# -*- coding: utf-8 -*-
"""Convert Fonduer candidates to Label Studio annotations."""

import json
import sqlalchemy
from typing import List, Any
import lxml.etree


class FonduerToLabelStudio:
    def __init__(self, lokal_files) -> None:
        self.lokal_files = lokal_files

    def make_type(self, FD_type: str) -> str:
        return FD_type[0].upper() + FD_type[1:]

    def seriealize_candidate(self, candidate):
        def modify_offset(offset, text):
            return offset + text.count(" ")

        # def modify_offset(offset, html_string, xpath):
        #     dom = lxml.etree.ElementTree(lxml.html.fromstring(html_string))
        #     results = dom.xpath(xpath)
        #     if results:
        #         text = results[0].text
        #     else:
        #         print(xpath)
        #         text = ""
        #     new_offset = offset - text.count(" ")
        #     if new_offset < 0:
        #         return 0
        #     return new_offset

        html_document = candidate.document.text

        version = "fonduer"
        score = 0.90

        results = []
        for spot in candidate:
            text = spot[0].get_span()
            if self.lokal_files:
                start = modify_offset(spot[0].char_start, text)
                # start = modify_offset(spot[0].char_start, html_document, spot[0].sentence.xpath)
                end = modify_offset(spot[0].char_end, text)
                # end = modify_offset(spot[0].char_end, html_document, spot[0].sentence.xpath)
            else:
                start = spot[0].char_start
                end = spot[0].char_end

            score = 0.80
            result = {
                "id": spot.id,
                "from_name": "ner",
                "to_name": "text",
                "type": "hypertextlabels",
                "readonly": False,
                "hidden": False,
                "score": score,
                "value": {
                    "start": spot[0].sentence.xpath.replace("/html/body", ""),
                    "end": spot[0].sentence.xpath.replace("/html/body", ""),
                    "startOffset": start + 1,
                    "endOffset": end + 2,
                    "text": text,
                    "hypertextlabels": [self.make_type(spot.type)],
                },
            }
            results.append(result)

        return {
            # "data": {"html": json.dumps(text)},
            "data": {"text": html_document},
            "annotations": [],
            "predictions": [{"model_version": version, "score": score, "result": results}],
        }

    def create_import(self, candidates: List[Any], fonduer_export_path: str) -> str:
        label_studio_import = []

        # Lokel files get "minified" Whitespaces and other infos are striped if impoted from local files
        # https://labelstud.io/guide/tasks.html#Import-HTML-data
        # If its true, we need to modify the offset based on the whitespaces.

        # serialize all candidates
        for candidate in candidates[0]:
            serialized = self.seriealize_candidate(candidate)
            label_studio_import.append(serialized)

        # write tasks
        with open(fonduer_export_path, "w") as file:
            json.dump(label_studio_import, file)
        return fonduer_export_path


# with open("my_export.json", "w") as file:
#     exp = cand_to_json(train_cands[0][0])
#     json.dump([exp], file)
