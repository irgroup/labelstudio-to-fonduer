# -*- coding: utf-8 -*-
"""Convert documents so that they can be used by Fonduer and Label Studio without beeing changed
during the process. This is crucial to reliably map the annotations back to the original documents.
"""
import html

import os
import shutil
from typing import Optional, List

import label_studio_sdk
import requests
from bs4 import BeautifulSoup, Comment
from bs4.formatter import HTMLFormatter
from fonduer import Meta
from fonduer.parser import Parser
from fonduer.parser.models import Document
from label_studio_sdk import Client
import lxml.etree

from LabelstudioToFonduer.util import init_logger
# from .util import init_logger
from LabelstudioToFonduer.fonduer_tools import save_create_project
# from .fonduer_tools import save_create_project
from LabelstudioToFonduer.document_processor import My_HTMLDocPreprocessor

logger = init_logger(__name__)


class UnsortedAttributes(HTMLFormatter):
    """BeautifulSoup HTMLFormatter that fixes the sorting of HTML attributes.
    This implemetation is based on the original implementation by BeauitfulSoup and can be found
    here: https://www.crummy.com/software/BeautifulSoup/bs4/doc/.
    """

    def attributes(self, tag):
        for k, v in tag.attrs.items():
            if k == "m":
                continue
            yield k, v


class DocumentConverter:
    """Convert documents so that they are natevly supportet by Fonduer and look the
    same after Fonduer processes them."""
    def __init__(self, flatten: List[str] = ["em"]):
        """Initialize the DocumentConverter.

        Args:
            flatten (List[str], optional): List of tags that should be flattened. Defaults to ["em"].
        """
        self.flatten = flatten


    def convert_one(
        self, document_path: str, output_path: str, encoding: Optional[str] = None
    ) -> None:
        """Document converter that prepares HTML documents for interchange between Label Studio and
        Fonduer. The document is opened with the given encoding if specified. If the encodimg is not
        known, please use the `check_conversion` function to check if the conversion succedes.
        The document is then parsed with BeautifulSoup and all comments are striped. Further, the
        HTML tag ordering is fixed and the document is saved to the output path using utf-8 encoding.

        Args:
            document_path (str): Path to the HTML document to be converted.
            output_path (str): Output path where the converted document should be saved.
            encoding (Optional[str], optional): If necessary, the encoding can be defined manualy.
                Defaults to None.
        """
        if document_path.endswith(".html"):
            # Fix \r encoding issue
            if encoding:
                with open(document_path, "r", encoding=encoding) as file:
                    html_string = file.read()
            else:
                with open(document_path, "r") as file:
                    html_string = file.read()
                

            root = lxml.html.fromstring(html_string)
            # flattens children of node that are in the 'flatten' list
            if self.flatten:
                lxml.etree.strip_tags(root, self.flatten)
            
            html_string = lxml.etree.tostring(root, encoding="unicode")

            soup = BeautifulSoup(html_string, "html.parser")

            # Fix comment strip issue
            for comments in soup.findAll(text=lambda text: isinstance(text, Comment)):
                comments.extract()

            # Fix Attribute sorting issue
            all_html_elements = soup.find_all("html")
            text = all_html_elements[0].prettify(formatter=UnsortedAttributes())

            filename = os.path.basename(document_path).replace("(", "").replace(")", "")

            with open(os.path.join(output_path, filename), "w", encoding="utf-8") as file:
                file.write(str(text))
                logger.info(f"Converted document `{filename}`.")

    def convert(self, input_: str, output_path: str, encoding: Optional[str] = None) -> None:
        """Converter wrapper function to convert a single document or a directory of documents.

        Args:
            input_ (str): Path to the directory of documents or a single document.
            output_path (str): Path or directory where the converted documents should be saved.
            encoding (Optional[str], optional): If necessary, the encoding can be defined manualy.
                Defaults to None.

        Raises:
            FileNotFoundError: If the input path does not exist.
        """
        # Is directory
        if os.path.isdir(input_):
            if not os.path.exists(output_path):
                os.makedirs(output_path)

            for file_name in os.listdir(input_):
                file_path = os.path.join(input_, file_name)
                self.convert_one(file_path, output_path, encoding)

        # Is file
        elif os.path.isfile(input_) and input_.endswith(".html"):
            self.convert_one(input_, output_path)

        elif not os.path.exists(input_):
            logger.critical(f" Abborting: File or directory {input_} does not exist.")
            raise FileNotFoundError(f"File or directory {input_} does not exist.")


class ConversionChecker:
    """Compare the different representations Label Studio and Fonduer may create from the same HTML
    document. This is useful to check if the conversion of the document is correct. The document is
    first converted to a format that is natively supportecomputerd by Fonduer. Then, the document is imported
    into Label Studio and Fonduer. The HTML representation of the document in Label Studio and
    Fonduer is compared. If the HTML representations are the same, the conversion was successful.
    """

    def __init__(
        self,
        label_studio_url: str,
        label_studio_api_key: str,
        fonduer_postgres_url: str,
        project_name: str = "tmp",
        paralel: int = 4,
    ) -> None:
        self.label_studio_url = label_studio_url
        self.label_studio_api_key = label_studio_api_key
        self.paralel = paralel
        self.fonduer_postgres_url = fonduer_postgres_url
        self.project_name = project_name
        self.labeling_config = """
        <View>
        <HyperTextLabels name="ner" toName="text">
            <Label value="Job" background="green"/>
            <Label value="City" background="blue"/>
        </HyperTextLabels>

        <View style="border: 1px solid #CCC;                border-radius: 10px;                padding: 5px">
            <HyperText name="text" value="$html" valueType="text" inline="true"/>
        </View>
        </View>
        """

    def process_fonduer(self, docs_path: str):
        """Process pipeline for Fonduer.

        Import a given document to Fonduer and export the documents back to the computer to
        compare the results and investigate any changes that might have occured.

        Args:
            docs_path (str): Path to the documents.
        """
        save_create_project(self.fonduer_postgres_url, self.project_name)

        # setup Fonduer
        session = Meta.init(self.fonduer_postgres_url + self.project_name).Session()
        doc_preprocessor = My_HTMLDocPreprocessor(docs_path, max_docs=100)

        # Import Document
        corpus_parser = Parser(session, structural=True, lingual=True, flatten=[])
        corpus_parser.apply(doc_preprocessor, parallelism=self.paralel)

        # Export parsed document
        documents = session.query(Document).all()
        html_str = documents[0].text
        filename = documents[0].name

        # FIX unescape at export level
        html_str = html.unescape(html_str)

        with open(
            os.path.join(docs_path, filename.replace("ORIGINAL_", "FONDUER_") + ".html"), "w"
        ) as file:
            file.write(html_str)

    def process_label_studio(self, docs_path: str):
        """Process pipeline for Label Studio.

        Import a given document to Label Studio and export the documents back to the computer to
        compare the results and investigate any changes that might have occured.

        Args:
            docs_path (str): Path to the documents.
        """

        def delete_all_tasks(project: label_studio_sdk.Project):
            """Delete all tasks from the temporary project.

            Args:
                project (label_studio_sdk.Project): Project for comparision.
            """
            r = requests.delete(
                self.label_studio_url + f"/api/projects/{project.id}/tasks/",
                headers={"Authorization": "Token " + self.label_studio_api_key},
            )
            assert r.status_code == 204, "Could not delete tasks"

        # Connect to the Label Studio API and check the connection
        ls = Client(url=self.label_studio_url, api_key=self.label_studio_api_key)
        assert ls.check_connection().get("status") == "UP", "Label Studio is not running"

        # setup project
        projects = {project.get_params()["title"]: project.id for project in ls.list_projects()}
        if self.project_name not in projects:
            project = ls.start_project(title=self.project_name, label_config=self.labeling_config)
        else:
            project = ls.get_project(projects[self.project_name])
            delete_all_tasks(project)

        # load file
        files = os.listdir(docs_path)
        for file_name in files:
            if file_name.startswith("ORIGINAL"):
                break
        with open(os.path.join(docs_path, file_name), "r") as file:
            html = file.read()

        # import html as task
        project.import_tasks(
            [
                {"html": html, "meta_info": {"file_name": file_name}},
            ]
        )

        # export html
        tasks = project.get_tasks()
        assert len(tasks) == 1, "Not exactly one task exported"

        tasks[0]["data"].keys()

        with open(
            os.path.join(docs_path, file_name.replace("ORIGINAL_", "LABEL-STUDIO_") + ".html"), "w"
        ) as file:
            file.write(html)

    def check(self, docs_path: str):
        """Import the given documents into Label Studio and Fonduer, then export them back and
        compare the results.

        Args:
            docs_path (str): Path to the documents.
        """

        def load_html(prefix, docs_path):
            file_names = os.listdir(docs_path)
            assert file_names, "No files in the directory"
            for file_name in file_names:
                if file_name.startswith(prefix):
                    break
            with open(os.path.join(docs_path, file_name)) as file:
                html_document = file.read()
            return html_document

        os.mkdir(self.project_name)

        # copy documents to path
        for file_name in os.listdir(docs_path):
            # construct full file path
            source = os.path.join(docs_path, file_name)
            destination = os.path.join(self.project_name, "ORIGINAL_"+file_name)
            # copy only files
            if os.path.isfile(source):
                shutil.copy(source, destination)

        # Import into systems
        self.process_fonduer(self.project_name)
        self.process_label_studio(self.project_name)

        # Load exports
        fonduer_html = load_html("FONDUER", docs_path)
        label_studio_html = load_html("LABEL-STUDIO", docs_path)
        original_html = load_html("ORIGINAL", docs_path)

        # Compare
        if original_html == label_studio_html:
            print("✓ Label Studio has not changed the HTML.")
            logger.info("✓ Label Studio has not changed the HTML.")
        else:
            logger.warning("✗ Label Studio has changed the HTML.")
        if fonduer_html == original_html:
            print("✓ Fonduer has not changed the HTML.")
            logger.info("✓ Fonduer has not changed the HTML.")
        else:
            logger.warning("✗ Fonduer has changed the HTML.")

        if fonduer_html == label_studio_html:
            print("✓ Fonduer and Label Studio have the same HTML.")
            logger.info("✓ Fonduer and Label Studio have the same HTML.")
        else:
            logger.warning("✗ Fonduer and Label Studio have different HTML.")
