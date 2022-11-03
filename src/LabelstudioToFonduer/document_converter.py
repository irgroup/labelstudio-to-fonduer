import os
from typing import Optional
from bs4 import BeautifulSoup, Comment
from bs4.formatter import HTMLFormatter


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

                soup = BeautifulSoup(html_string, "html.parser")

            # Fix comment strip issue
            for comments in soup.findAll(text=lambda text: isinstance(text, Comment)):
                comments.extract()

            all_html_elements = soup.find_all("html")
            text = all_html_elements[0].prettify(formatter=UnsortedAttributes())
            # text = all_html_elements[0].prettify(formatter=None)

            filename = os.path.basename(document_path).replace("(", "").replace(")", "")

            with open(os.path.join(output_path, filename), "w", encoding="utf-8") as file:
                file.write(str(text))

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
            raise FileNotFoundError(f"File or directory {input_} does not exist.")

    @staticmethod
    def check_conversion():
        pass
        # TODO: implement Conversion checker
