# -*- coding: utf-8 -*-
"""Convert Fonduer candidates to Label Studio annotations."""

import json
import re
from typing import Any, Dict, List, Tuple, Union

import lxml.etree


def green(text, from_, to):
    text_highlight = text[:from_] + "\x1b[6;30;42m" + text[from_:to] + "\x1b[0m" + text[to:]
    return text_highlight


def log_offset(span, html_document, offset_start, offset_end, offset_plus, xpath_start):
    dom = lxml.etree.ElementTree(lxml.html.fromstring(html_document))
    results = dom.xpath(xpath_start)

    if results:
        html_span = results[0].text_content()

        print(f"XPath:\t{xpath_start}")

        print(
            f"Offset:\toffset_start: {offset_start-offset_plus} offset_end: {offset_end-offset_plus}"
        )
        print(f"Plus:\t{offset_plus}")
        print("Span:\t" + span)
        print(f"Raw:\t{repr(html_span)}")
        print(f"Marked:\t{green(html_span, offset_start, offset_end)}\n")

    else:
        print("ERROR: no span found from XPath")


def get_offsets(span: str, sentence: str) -> List[Tuple[int, int]]:
    """Get all occurences of a span in a sentence and return the offset

    Args:
        span (str): Span to be matched.
        sentence (str): Sentence to be searched.

    Returns:
        List[Tuple[int, int]]: List of offsets.
    """
    span_escaped = re.escape(span)
    result = re.finditer(span_escaped, sentence)
    offsets = []
    for match in result:
        offsets.append((match.start(), match.end()))
    return offsets


class FonduerToLabelStudio:
    """Transfere Fonduer candidates to Label Studio Labes."""

    def seriealize_relation(self, relation: Any, confidence: float = 0.00) -> List[Dict[str, Any]]:
        """Serialize a Fonduer candidate relation into a Label Studio annotated relation of entities.

        The Fonduer candidate is parsed and modified to create a Label Studio annotation from it.
        First the Relation is created and then all enteties are added. The offset is modified to
        match the HTML element span, the XPath is modifies to use the body element as root.

        Args:
            relation (Any): Fonduer candidate relation.
            confidence (Float): confidence score of the relation. Defaults to 0.00.

        Returns:
            List[Dict[str, Any]]: List of serialized relations and entities.
        """

        def calculate_offset_plus(
            fd_span: str, html_string: str, xpath: str, offset_start: int
        ) -> int:
            """Calculate addititional offset from the html element.

            Fondue calculates the offset based on the sentence only. If the HTML element located by
            the XPath may contain further sentences and the HTML tag may also contain training
            whitespaces, an additional offset may be needed.
            This offset is calculated by searching the Fonduer Span in the HTML element and
            subtracting the offset from fonuer.

            Args:
                fd_span (str): Text of the entity from Fonduer.
                html_string (str): Full HTML string to construct the DOM and search the XPath.
                xpath (str): XPath to the HTML element with the span init.
                offset_start (int): Fonduer offset.

            Returns:
                int: Additional character offset.
            """
            dom = lxml.etree.ElementTree(lxml.html.fromstring(html_string))  # Create the dom
            results = dom.xpath(xpath)

            if len(results) > 1:
                print("ERROR: more than one result")

            if results:
                html_span = results[0].text_content()

                # offset_plus = html_span.find(fd_span)  # Search for the FD span in the LS span

                # if string is multiple times in the context, the occurence with the closest offset
                # to the offset from Fonduer is used
                matches = get_offsets(fd_span, html_span)

                if len(matches) > 1:
                    candidates = []
                    for candidate in matches:
                        candidates.append(abs(candidate[0] - offset_start))
                    index = candidates.index(min(candidates))
                    offset_plus = matches[index][0]
                elif len(matches) == 1:
                    offset_plus = matches[0][0]

                elif len(matches) == 0:
                    raise ValueError("Span not found in sentence")

                if offset_plus < 1:
                    print("ERROR: offset_plus < 1")
                    return 0
                return offset_plus - offset_start

            else:
                print("ERROR: no span found from XPath")
                return 0

        # html text
        html_document = relation.document.text
        results = []

        # add relation
        results.append(
            {
                "from_id": relation[0].id,
                "to_id": relation[1].id,
                "type": "relation",
                "direction": "right",
                "readonly": False,
            }
        )

        # add enteties
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

            # TODO: improve logging
            if True:
                log_offset(text, html_document, offset_start, offset_end, offset_plus, xpath_start)

            result = {
                "id": entity.id,
                "from_name": "ner",
                "to_name": "text",
                "type": "hypertextlabels",
                "readonly": False,
                "hidden": False,
                "score": confidence,
                "value": {
                    "start": xpath_start.replace("/html/body", ""),
                    "end": xpath_end.replace("/html/body", ""),
                    "startOffset": offset_start,
                    "endOffset": offset_end,
                    "text": text,
                    "hypertextlabels": [entity.type[0].upper() + entity.type[1:]],
                },
            }
            results.append(result)

        return results

    def create_export(
        self, candidates: List[Any], fonduer_export_path: str = ""
    ) -> Union[str, List[Any]]:
        """Create a Label Studio import file from Fonduer candidates.

        Args:
            candidates (List[Any]): Candidates from Fonduer.
            fonduer_export_path (str, optional): Desired location for the Label Studio import file. Defaults to "".

        Returns:
            Union[str, List[Any]]: Import dictionary or the
            path where the import file is saved.
        """
        documents = {}

        for relation in candidates[0]:  # serialize all candidates
            if relation.document.name not in documents:  # Goup by documents
                # Create base document
                documents[relation.document.name] = {
                    "id": relation.document.name,
                    "data": {
                        "text": relation.document.text,
                    },
                    "annotations": [{"model_version": 0, "score": 0, "result": []}],
                }

            # Add relations of document
            documents[relation.document.name]["annotations"][0]["result"].extend(
                self.seriealize_relation(relation)
            )

        fonduer_export = list(documents.values())

        if fonduer_export_path:
            with open(fonduer_export_path, "w") as file:
                json.dump(fonduer_export, file)
            return fonduer_export_path
        else:
            return fonduer_export
