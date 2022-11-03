# -*- coding: utf-8 -*-
"""
*    Title: Fonduer: Knowledge Base Construction from Richly Formatted Data
*    Author: Wu, Sen and Hsiao, Luke and Cheng, Xiao and Hancock, Braden and Rekatsinas, Theodoros 
            and Levis, Philip and Ré, Christopher,
*    Date: 3.11.2022
*    Code version: v0.9.0
*    Availability: https://github.com/HazyResearch/fonduer/blob/433a75d0d7bfb59e5ddbc9eb6e6f9fe9428a6fb3/src/fonduer/parser/preprocessors/html_doc_preprocessor.py

Original License:

MIT License

Copyright (c) 2018 HazyResearch

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.


Modifications:
This HTML Document processor is heavily based on the original Fonduer HTML Document processor. 
Only the document openng process is modified to not use `codecs.open` but `open` instead.
This might solve encoding issues.
"""
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
