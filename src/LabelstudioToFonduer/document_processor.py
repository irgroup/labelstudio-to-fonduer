# TODO: check licensing on that file
from fonduer.parser.preprocessors.doc_preprocessor import DocPreprocessor
from typing import Iterator
from bs4 import BeautifulSoup
import os
from fonduer.parser.models import Document


class My_HTMLDocPreprocessor(DocPreprocessor):
    """A ``Document`` generator for HTML files."""

    def _parse_file(self, document_path: str, file_name: str) -> Iterator[Document]:
        with open(document_path, "r", encoding=self.encoding) as file:
            soup = BeautifulSoup(file, "lxml")
            all_html_elements = soup.find_all("html")
            if len(all_html_elements) != 1:
                raise NotImplementedError(
                    f"Expecting exactly one html element per html file: {file_name}"
                )
            text = all_html_elements[0]
            name = os.path.basename(document_path)[: os.path.basename(document_path).rfind(".")]
            stable_id = self._get_stable_id(name)
            yield Document(
                name=name,
                stable_id=stable_id,
                text=str(text),
                meta={"file_name": file_name},
            )

    def __len__(self) -> int:
        """Provide a len attribute based on max_docs and number of files in folder."""
        num_docs = min(len(self.all_files), self.max_docs)
        return num_docs

    def _can_read(self, fpath: str) -> bool:
        return fpath.lower().endswith("html")  # includes both .html and .xhtml
