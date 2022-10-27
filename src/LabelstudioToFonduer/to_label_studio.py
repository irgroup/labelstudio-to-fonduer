# -*- coding: utf-8 -*-
"""Convert Fonduer candidates to Label Studio annotations."""

import json
import sqlalchemy
from typing import List, Any
import lxml.etree


def green(text, from_, to):
    text_highlight = text[:from_] + "\x1b[6;30;42m" + text[from_:to] + "\x1b[0m" + text[to:]
    return text_highlight


def log_offset(span, html_document, offset_start, offset_end, offset_plus, xpath_start):

    dom = lxml.etree.ElementTree(lxml.html.fromstring(html_document))
    results = dom.xpath(xpath_start)

    if results:
        HTML_span = results[0].text_content()

        print(f"XPath:\t{xpath_start}")

        print(
            f"Offset:\toffset_start: {offset_start-offset_plus} offset_end: {offset_end-offset_plus}"
        )
        print(f"Plus:\t{offset_plus}")
        print("Span:\t" + span)
        print(f"Raw:\t{repr(HTML_span)}")
        print(f"Marked:\t{green(HTML_span, offset_start, offset_end)}\n")

    else:
        print("ERROR: no span found from XPath")


class FonduerToLabelStudio:
    def __init__(self, lokal_files) -> None:
        self.lokal_files = lokal_files

    def make_type(self, FD_type: str) -> str:
        return FD_type[0].upper() + FD_type[1:]

    def seriealize_relation(self, relation):
        def calculate_offset_plus(FD_span, html_string, xpath, offset_start):
            dom = lxml.etree.ElementTree(lxml.html.fromstring(html_string))
            results = dom.xpath(xpath)

            if len(results) > 1:
                print("ERROR: more than one result")

            if results:
                HTML_span = results[0].text_content()

                offset_plus = HTML_span.find(FD_span)  # Search for the FD span in the LS span

                if offset_plus < 1:
                    print("ERROR: offset_plus < 1")
                    return 0
                return offset_plus - offset_start

            else:
                print("ERROR: no span found from XPath")
                return 0

        html_document = relation.document.text

        score = 0.90

        results = []
        # add relation
        results.append(
            {
                "from_id": relation[0].id,
                "to_id": relation[1].id,
                "type": "relation",
                "direction": "right",
            }
        )

        # add entetys
        for entity in relation:
            span_mention = entity[0]

            xpath_start = span_mention.sentence.xpath
            xpath_end = span_mention.sentence.xpath

            text = span_mention.get_span()

            offset_plus = calculate_offset_plus(
                text,
                html_document,
                xpath_start,
                span_mention.char_start,
            )

            offset_start = span_mention.char_start + offset_plus
            offset_end = span_mention.char_end + offset_plus + 1

            if True:
                log_offset(text, html_document, offset_start, offset_end, offset_plus, xpath_start)

            score = 0.80

            result = {
                "id": entity.id,
                "from_name": "ner",
                "to_name": "text",
                "type": "hypertextlabels",
                "readonly": False,
                "hidden": False,
                "score": score,
                "value": {
                    "start": xpath_start.replace("/html/body", ""),
                    "end": xpath_end.replace("/html/body", ""),
                    "startOffset": offset_start,
                    "endOffset": offset_end,
                    "text": text,
                    "hypertextlabels": [self.make_type(entity.type)],
                },
            }
            results.append(result)

        return results

    def create_import(self, candidates: List[Any], fonduer_export_path: str) -> str:

        documents = {}
        # serialize all candidates
        for relation in candidates[0]:
            if relation.document.name not in documents:
                documents[relation.document.name] = {
                    "id": relation.document.name,
                    "data": {
                        "text": relation.document.text,
                    },
                    "predictions": [{"model_version": 0, "score": 0, "result": []}],
                }

            documents[relation.document.name]["predictions"][0]["result"].extend(
                self.seriealize_relation(relation)
            )

            label_studio_import = list(documents.values())

        # write tasks
        with open(fonduer_export_path, "w") as file:
            json.dump(label_studio_import, file)
        return fonduer_export_path
