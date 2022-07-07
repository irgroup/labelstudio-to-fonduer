import json
import re
import warnings
import logging
from typing import Any, Dict, List, Set, Tuple, Optional
import lxml

import fonduer
from pandas import to_timedelta  # type: ignore
import sqlalchemy
from bs4 import BeautifulSoup
from fonduer.parser.models import Document, Sentence
from lxml import etree  # type: ignore

# TBODY_REGEX = r"/tbody(\[\d+\])?"
logging.basicConfig(format="[%(asctime)s][%(levelname)s] %(message)s", level="info")


class Export:
    def __init__(self, session: sqlalchemy.orm.session.Session, path: str) -> None:
        self.session = session
        self.path = path
        self.spots, self.relations, self.id_label = self.parse(self.path, self.session)
        self.spots_table = self._tabulate()
        self.labels = self._get_labels()
        self.entity_types = set(self.labels.keys())

    def _get_filename(self, label_studio_str: str) -> str:
        """Parse the original filename from the filename rovided by labels studio by stripping the ID and ending.

        Args:
            label_studio_str (str): Filename provided by the labelstudio export.

        Returns:
            str: Clean filename.
        """
        split = label_studio_str.split("-")  # strip id
        full = "-".join(split[1:])
        split = full.split(".")
        result = "".join(split[:-1])
        return result

    def _get_html_tree_from_string(self, html_string: str) -> etree._ElementTree:
        """Parse an HTML string into a rooted eement tree.

        Args:
            html_string (str): HTML string of a full website.

        Returns:
            etree._ElementTree: Tree object for further use.
        """
        html_string = BeautifulSoup(html_string, "html5lib")
        return etree.ElementTree(lxml.html.fromstring(str(html_string)))

    def _get_absolute_xpath(
        self, relative_xpath: str, dom: etree._ElementTree
    ) -> Optional[str]:
        """Convert an relative XPATH string into an absolute one by searching the provided DOM object
        and returning the absolute XPATH of the found element.

        Args:
            rel_xpath (str): Relative XPATH to be transformed into an absolute one.
            dom (etree._ElementTree): DOM object of the full document to be searched by the XPATH.

        Returns:
            str: Absolute XPATH to the relative XPATH.
        """
        # The XPaths retrieved from Labes Studio contain 'tbody' elements, wich might not be in the actual HTMLs annotated. This is because the LS Frontend, as it is written in Java Script, operates on the DOM of the HTML, not the actual string and adds "missing" 'tbody' tags. To make use of the XPaths out of LS the additional 'tbody' elements are deleted from the XPath. Source: https://stackoverflow.com/questions/18241029/why-does-my-xpath-query-scraping-html-tables-only-work-in-firebug-but-not-the
        # relative_xpath = re.sub(
        #     TBODY_REGEX, "", relative_xpath
        # )  # delete tbody elements
        res = dom.xpath("/" + relative_xpath)
        if not res:
            return None
        else:
            res = res[0]
        # print(res.getparent())
        # print(dom.getpath(res.getparent()))
        element = res.getparent()
        if element.tail:
            element = element.getparent()
        xpath = dom.getpath(element)
        xpath = xpath.replace("html[1]", "html")
        if xpath.endswith("/span"):
            xpath = xpath[:-5]
        return xpath

    def _tabulate(self) -> List[Any]:
        """Generate a tabulated list of tuples of the relations. Each tuple is a relation consisting of
        the fields: fonduer_doc_id, text and fd_sentence_id for the first entity and fonduer_doc_id and
        text, fd_sentence_id for the second entity.

        Returns:
            List[Tuple[str]]: Tabulated relations.
        """
        tabulated = []
        for relation in self.relations:
            entety_1 = self.spots.get(relation[0])
            entety_2 = self.spots.get(relation[1])
            if (
                entety_1 and entety_2
            ) is None:  # ignoring files without xpath found (one is none)
                continue
            assert entety_1["fonduer_doc_id"] == entety_2["fonduer_doc_id"]
            tabulated.append(
                (
                    entety_1["fonduer_doc_id"],
                    entety_1["text"],
                    entety_1["fd_sentence_id"],
                    # entety_1["ls_spot_offsets"][0],
                    # entety_1["ls_spot_offsets"][1],
                    entety_2["fonduer_doc_id"],
                    entety_2["text"],
                    entety_2["fd_sentence_id"],
                    # entety_2["ls_spot_offsets"][0],
                    # entety_2["ls_spot_offsets"][1],
                )
            )
        return tabulated

    def _get_labels(self) -> Dict[str, Set[str]]:
        """Extract the labels of the entities and return a dictionary with a set of labels per entity type.

        Returns:
            Dict[str, Set[str]]: Dict with all entity types and a set of the according labels.
        """

        entity_labels: Dict[str, Set[str]] = {}
        for spot in self.spots:
            if not entity_labels.get(self.spots[spot]["label"]):
                entity_labels[self.spots[spot]["label"]] = set()
            entity_labels[self.spots[spot]["label"]].add(self.spots[spot]["text"])
        return entity_labels

    def parse(self, export_path: str, session: sqlalchemy.orm.session.Session) -> Any:
        """Parse a label studio export path into spots, relations and ids. After initially parsing the
        json file, the Fonfuer document ID is retrieved based on the filename. Further, the sentence IDs
        of all spots are retrieved by the XPATH which is converted from the relative XPATH provided by
        label studio into the absolute XPATH. Based on annotations without a `value` relations are
        identified and extrected. To link between spots in a relation a patch dictionary with the label
        studio spot ids as key and the label as value is created.

        Args:
            export_path (str): Path to the Labelstudio export.
            session (sqlalchemy.orm.session.Session): Session to connect with the fonduer database.

        Returns:
            spots (Dict[str, str]): dictionnarry of all spots.
            relations (List[str]): List of all relations.
            id_label (Dict[str, str]): Patch dict with spot IDs and labels.
        """
        spots = {}
        relations = []
        id_label = {}

        with open(export_path, "r") as fin:
            export = json.load(fin)

        for annotated_doc in export:

            filename = self._get_filename(annotated_doc["file_upload"])

            fonduer_doc_id_results = (
                session.query(Document.id).filter(Document.name == filename).first()
            )
            if fonduer_doc_id_results == None:
                logging.warning(
                    f'Annotated file "{filename}" could not be found in fonduer.'
                )
                continue

            fonduer_doc_id = str(fonduer_doc_id_results[0])

            # Depending on the template used in LS the key may vary.
            if not annotated_doc["data"].get("html"):
                assert len(list(annotated_doc["data"].keys())) == 1
                html_key = list(annotated_doc["data"].keys())[
                    0
                ]  # take the first key and assume the html is in there as value
            else:
                html_key = "html"

            tree = self._get_html_tree_from_string(
                annotated_doc["data"][html_key]
            )  # recreate html tree for doc
            # self.tree = tree

            for annotations in annotated_doc["annotations"]:
                if not annotations["result"]:  # ignore files wich are not annotated
                    continue
                for entety in annotations["result"]:
                    if entety.get("value"):
                        xpath_rel = entety["value"]["start"]
                        xpath_abs = self._get_absolute_xpath(xpath_rel, tree)

                        if not xpath_abs:
                            logging.warning(f'no xpath found - "{filename}"')
                            continue

                        spot_text = entety["value"]["text"].replace("\\n", "").strip()

                        # print(xpath_abs)
                        fd_sentence_id = (
                            session.query(Sentence.id, Sentence.text)
                            .filter(
                                Sentence.document_id == fonduer_doc_id,
                                Sentence.xpath == xpath_abs,
                                Sentence.text.contains(spot_text),
                            )
                            .all()
                        )

                        # print(fd_sentence_id)
                        label = entety["value"]["hypertextlabels"][0]
                        ls_ID = entety["id"]
                        id_label[ls_ID] = label

                        if not fd_sentence_id:
                            logging.warning(f'No sentence found - "{filename}"')
                            # if label == "Title":
                            print(
                                "| "
                                + " | ".join(
                                    [filename, entety["value"]["text"], xpath_abs]
                                )
                                + " |"
                            )
                            continue
                        elif len(fd_sentence_id) > 1:
                            logging.warning(f'Multiple sentences found - "{filename}"')
                            print(fd_sentence_id)

                        spots[ls_ID] = {
                            # "xpath_rel": xpath_rel,
                            "xpath_abs": xpath_abs,
                            "label": label,
                            "text": spot_text,
                            "ls_ID": ls_ID,
                            "fd_sentence_id": str(fd_sentence_id[0][0]),
                            "filename": filename,
                            "fonduer_doc_id": fonduer_doc_id,
                            "ls_spot_offsets": (
                                str(entety["value"]["startOffset"]),
                                str(entety["value"]["endOffset"]),
                            ),
                        }

                    else:
                        relations.append(
                            (
                                entety["from_id"],
                                entety["to_id"],
                                entety["hypertextlabels"],
                            )
                        )

        if not relations:
            labels = []

            # create label
            for spot in spots.keys():
                label = spots[spot]["label"]

                if label not in labels:
                    labels.append(label)

            logging.warning("No relations described, adding annotations now.")
            for annotated_doc in export:
                for annotations in annotated_doc["annotations"]:
                    if len(annotations["result"]) != 2:
                        logging.warning(
                            str(
                                "Skipping document: "
                                + str(annotated_doc["id"])
                                + ". Not 2 annotations."
                            )
                        )
                        continue

                    if (
                        annotations["result"][0]["value"]["hypertextlabels"][0]
                        == labels[0]
                    ):
                        from_id = annotations["result"][1]["id"]
                        to_id = annotations["result"][0]["id"]
                    elif (
                        annotations["result"][1]["value"]["hypertextlabels"][0]
                        == labels[0]
                    ):
                        from_id = annotations["result"][0]["id"]
                        to_id = annotations["result"][1]["id"]

                    relations.append((from_id, to_id, None))

        return spots, relations, id_label

    # def is_gold(self, cand: fonduer.candidates.models.Candidate) -> int:
    def is_gold(self, cand) -> int:
        """Check if a provided candidate is gold labeld entety.

        Args:
            cand (fonduer.candidates.models.Candidate): A fonduer candidate to be checked.

        Returns:
            int: 1 if the candidate is gold labeled, 0 if not.
        """
        canddidate_tuple = (
            str(cand[1].document_id),
            str(cand[1].context.get_span()),
            str(cand[1].context.sentence.id),
            # str(cand[1].context.char_start),
            # str(cand[1].context.char_end + 1),
            str(cand[0].document_id),
            str(cand[0].context.get_span()),
            str(cand[0].context.sentence.id),
            # str(cand[0].context.char_start + 1),
            # str(cand[0].context.char_end + 2),
        )
        if canddidate_tuple in self.spots_table:
            return 1
        return 0
