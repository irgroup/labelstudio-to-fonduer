import json
import logging
import os
import re
import shutil
from typing import Any, Dict, List, overload

import lxml
from bs4 import BeautifulSoup
from fonduer.parser.models import Document, Sentence
from lxml.html import document_fromstring, fromstring
from lxml.html.clean import clean_html
import pandas as pd
from collections import defaultdict

# from lxml.html.soupparser import fromstring
from matplotlib.pyplot import text

# logging.basicConfig(format="[%(asctime)s][%(levelname)s] %(message)s", level="warning")


class Export_Entity:
    def __init__(
        self,
        start_offset: int,
        end_offset: int,
        text: str,
        label: str,
        xpath: str,
        export_document,
    ):
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.text = text.replace("\\n", "").strip()
        self.label = label
        self.xpath = xpath
        self.export_documents = export_document

    def find_candidates_in_db(self, session) -> bool:
        result = False
        candidates = (
            session.query(
                Sentence.char_offsets, Sentence.text, Sentence.xpath, Sentence.id
            )
            .filter(
                Sentence.document_id == self.export_documents.document_id,
                Sentence.xpath == self.xpath,
                Sentence.text.contains(self.text),
            )
            .all()
        )
        if not candidates:
            logging.warning(
                f'No candidates found - Document: "{self.export_documents.filename}", Entety: "{self.text}"'
            )
            result = False

        elif len(candidates) == 1:
            self.sentence_id = candidates[0][3]
            result = True

        else:
            logging.warning(
                f'Multiple candidates found - Document: "{self.export_documents.filename}", Entety: "{self.text}"'
            )
            result = False

        self.candidates = []
        for candidate in candidates:
            self.candidates.append(
                (
                    self.export_documents.document_id,
                    self.export_documents.filename,
                    self.label,
                    candidate[0],
                    candidate[0],
                    candidate[1],
                    candidate[2],
                    candidate[3],
                    "Candidate",
                )
            )
        return result

    def serielize(self):
        return {
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "text": self.text,
            "label": self.label,
            "xpath": self.xpath,
        }

    def tabulate(self, candidates: bool):
        sentence_id = self.sentence_id if hasattr(self, "sentence_id") else ""
        row = (
            "",
            self.export_documents.filename,
            self.label,
            self.start_offset,
            self.end_offset,
            self.text,
            self.xpath,
            sentence_id,
            "",
        )
        if hasattr(self.export_documents, "document_id"):
            row = (self.export_documents.document_id,) + row[1:-1] + ("Gold",)
        yield row

        if hasattr(self, "candidates") and candidates:
            for candidate in self.candidates:
                yield candidate
        elif candidates:
            logging.info(
                "No candidates found. Please call the `find_candidates_in_db()` method first."
            )


class Default_Entety_Parser:
    def __init__(self, dom):
        self.dom = dom

    def get_absolute_xpath(self, relative_xpath) -> str:
        results = self.dom.xpath("/" + relative_xpath)
        if not results:
            return None
        else:
            results = results[0]
        # print(res.getparent())
        # print(dom.getpath(res.getparent()))
        element = results.getparent()
        if element.tail:
            element = element.getparent()
        absolute_xpath = self.dom.getpath(element)
        absolute_xpath = absolute_xpath.replace("html[1]", "html")
        if absolute_xpath.endswith("/span"):
            absolute_xpath = absolute_xpath[:-5]
        return absolute_xpath

    def parse(self, entety_list: List[Dict[str, Any]], export_document):
        for entety in entety_list:
            if not entety.get("value"):
                continue
            start_offset = entety["value"]["startOffset"]
            end_offset = entety["value"]["endOffset"]
            text = entety["value"]["text"]
            label = entety["value"]["hypertextlabels"][0]
            xpath = self.get_absolute_xpath(entety["value"]["start"])

            yield Export_Entity(
                start_offset, end_offset, text, label, xpath, export_document
            )


class Export_Document:
    def __init__(
        self,
        export: Dict[str, Any],
        base_dir: str = "tmp",
        entety_parser=Default_Entety_Parser,
    ):
        self.base_dir = base_dir
        self.filename = "-".join(export["file_upload"].split("-")[-1:])
        self.html = self.clean_html(export)
        self.path = self.write_doc()

        self.entety_parser = entety_parser(self.html)
        self.entetys = list(
            self.entety_parser.parse(export["annotations"][0]["result"], self)
        )  # only one annotator per document is supporte t at the moment

    def clean_html(self, export: Dict[str, Any]):
        html_key = list(export["data"].keys())[0]
        html_string = export["data"][html_key]

        html_string = re.sub(r"(\w)\s\s+(\w)", r"\g<1> \g<2>", html_string)

        html_string = BeautifulSoup(html_string, "html5lib")

        # html_string = BeautifulSoup(html_string)
        # html_string = lxml.etree.ElementTree(fromstring(str(html_string)))
        html_string = lxml.etree.ElementTree(document_fromstring(str(html_string)))
        # html_string = clean_html(html_string)

        return html_string

    def write_doc(self):
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

        path = os.path.join(self.base_dir, self.filename)
        self.html.write(path)
        return path

    def find_doc_in_db(self, session) -> bool:
        filename_short = self.filename[:-5]
        document_id = (
            session.query(Document.id)
            .filter(
                Document.name == filename_short,
            )
            .first()
        )
        if len(document_id) != 1:
            logging.warning("Document_id is ambigues.")
            return False
        else:
            self.document_id = document_id[0]

            # update document in the enteties
            for entety in self.entetys:
                entety.export_documents.document_id = self.document_id
            return True

    def find_candidates_in_db(self, session) -> bool:
        results = []
        for entety in self.entetys:
            results.append(entety.find_candidates_in_db(session))
        if all(results):
            return True
        else:
            return False

    def serielize(self):
        document_serielized = {
            "filename": self.filename,
            "path": self.path,
            "entetys": [entety.serielize() for entety in self.entetys],
        }
        if self.document_id:
            document_serielized["document_id"] = self.document_id

        return document_serielized

    def tabulate(self, candidates: bool):
        for entety in self.entetys:
            for row in entety.tabulate(candidates):
                yield row


class Export:
    def __init__(self, export_path, base_dir: str = "tmp") -> None:
        self.export_path = export_path
        self.base_dir = base_dir
        self.export_documents = self.parse_export()
        self.texts = self.get_texts()
        self.ngrams = self.get_ngram_size()

    def parse_export(self, override: bool = True):
        with open(self.export_path, "r") as file:
            self.export = json.load(file)

        # Prepare directory
        if os.path.exists(self.base_dir):
            if override:
                shutil.rmtree(self.base_dir)
                os.makedirs(self.base_dir)
        else:
            os.makedirs(self.base_dir)

        # Parse labeled docs
        documents = []
        for document in self.export:
            parsed_document = Export_Document(document, base_dir=self.base_dir)
            documents.append(parsed_document)
        return documents

    def create_table(self, candidates: bool, pandas: bool = False, csv: bool = False):
        table = []
        for document in self.export_documents:
            table.extend(document.tabulate(candidates=candidates))

        columns = [
            "Doc_ID",
            "Filename",
            "Label",
            "Offset_start",
            "Offset_stop",
            "Text",
            "XPath",
            "Sentence_ID",
            "Type",
        ]
        if pandas:
            table = pd.DataFrame(table, columns=columns)
        if csv:
            pd.DataFrame(table, columns=columns).to_csv("table.csv", index=False)

        return table

    def get_ngram_size(self):
        entety_lenghths = defaultdict(set)

        for document in self.export_documents:
            for entety in document.entetys:
                entety_lenghths[entety.label].add(len(entety.text.split(" ")))

        ngrams = {}
        for label in entety_lenghths.keys():
            ngrams[label] = {
                "min": min(entety_lenghths[label]),
                "max": max(entety_lenghths[label]),
            }
        return ngrams

    def get_texts(self):
        texts = defaultdict(set)
        for document in self.export_documents:
            for entety in document.entetys:
                texts[entety.label].add(entety.text)
        return texts

    def is_gold(self, cand):
        """Check if a provided candidate is gold labeld entety.

        Args:
            cand (fonduer.candidates.models.Candidate): A fonduer candidate to be checked.

        Returns:
            int: 1 if the candidate is gold labeled, 0 if not.
        """
        canddidate_tuple = (
            cand[0].document_id,
            cand[0].context.get_span(),
            cand[0].context.sentence.id,
            # str(cand[1].context.char_start),
            # str(cand[1].context.char_end + 1),
            cand[1].document_id,
            cand[1].context.get_span(),
            cand[1].context.sentence.id,
            # str(cand[0].context.char_start + 1),
            # str(cand[0].context.char_end + 2),
        )
        if canddidate_tuple in self.gold_table:
            return 1
        return 0

    def create_gold_function(self, session):

        # Create gold table for comparision
        self.gold_table = []

        for document in self.export_documents:
            if len(document.entetys) != 2:
                continue
            # Enrich entetys with db content
            if document.find_doc_in_db(
                session=session
            ) and document.find_candidates_in_db(session=session):

                entety_1 = document.entetys[0]
                entety_2 = document.entetys[1]
                self.gold_table.append(
                    (
                        entety_1.export_documents.document_id,
                        entety_1.text,
                        entety_1.sentence_id,
                        entety_2.export_documents.document_id,
                        entety_2.text,
                        entety_2.sentence_id,
                    )
                )
