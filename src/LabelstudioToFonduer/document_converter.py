import os
from bs4 import BeautifulSoup, Comment
from bs4.formatter import HTMLFormatter


class UnsortedAttributes(HTMLFormatter):
    def attributes(self, tag):
        for k, v in tag.attrs.items():
            if k == "m":
                continue
            yield k, v


class DocumentConverter:
    """Convert documents so that they are natevly supportet by Fonduer and look the
    same after Fonduer processes them."""

    def convert_one(self, document_path: str, output_path: str) -> None:
        encoding = "utf-8-sig"  # TODO: detect encoding automatically and correct (Fonduer does not pick up the BOM)

        if document_path.endswith(".html"):
            # Fix \r encoding issue
            with open(document_path, "r", encoding=encoding) as file:
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

    def convert(self, input_: str, output_path: str) -> None:
        # Is directory
        if os.path.isdir(input_):
            if not os.path.exists(output_path):
                os.makedirs(output_path)

            for file_name in os.listdir(input_):
                file_path = os.path.join(input_, file_name)
                self.convert_one(file_path, output_path)

        # Is file
        elif os.path.isfile(input_):
            self.convert_one(input_, output_path)

        # TODO: rais file error if not supported
