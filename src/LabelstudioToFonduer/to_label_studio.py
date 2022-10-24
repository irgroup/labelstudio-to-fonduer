# -*- coding: utf-8 -*-
"""Convert Fonduer candidates to Label Studio annotations."""

import json
import sqlalchemy
from typing import List, Any


class FonduerToLabelStudio:
    def make_type(self, FD_type: str) -> str:
        return FD_type[0].upper() + FD_type[1:]

    def seriealize_candidate(self, candidate):
        text = candidate.document.text

        version = "fonduer"
        score = 0.90

        results = []
        for spot in candidate:
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
                    "start": spot[0].sentence.xpath,
                    "end": spot[0].sentence.xpath,
                    "startOffset": spot[0].char_start,
                    "endOffset": spot[0].char_end,
                    "text": spot[0].get_span(),
                    "hypertextlabels": [self.make_type(spot.type)],
                },
            }
            results.append(result)

        return {
            # "data": {"html": json.dumps(text)},
            "data": {"text": text},
            "annotations": [],
            "predictions": [{"model_version": version, "score": score, "result": results}],
        }

    def create_import(self, candidates: List[Any], fonduer_export_path: str) -> str:
        label_studio_import = []

        # serialize all candidates
        for candidate in candidates[0]:
            serialized = self.seriealize_candidate(candidate)
            label_studio_import.append(serialized)

        # write tasks
        with open(fonduer_export_path, "w") as file:
            json.dump(label_studio_import, file)


# with open("my_export.json", "w") as file:
#     exp = cand_to_json(train_cands[0][0])
#     json.dump([exp], file)
