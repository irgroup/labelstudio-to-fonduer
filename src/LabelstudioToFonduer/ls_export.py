import json
from typing import Dict, List, Tuple, Set, Any

import fonduer  # type: ignore
import sqlalchemy
from bs4 import BeautifulSoup
from fonduer.parser.models import Document, Sentence
from lxml import etree  # type: ignore


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
        full = "".join(split[1:])
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
        soup = BeautifulSoup(html_string, features="lxml")
        dom = etree.HTML(str(soup))
        root = dom.getroottree()
        return root

    def _get_absolute_xpath(self, rel_xpath: str, dom: etree._ElementTree) -> str:
        """Convert an relative XPATH string into an absolute one by searching the provided DOM object
        and returning the absolute XPATH of the found element.

        Args:
            rel_xpath (str): Relative XPATH to be transformed into an absolute one.
            dom (etree._ElementTree): DOM object of the full document to be searched by the XPATH.

        Returns:
            str: Absolute XPATH to the relative XPATH.
        """
        res = dom.xpath("/" + rel_xpath)[0]
        return dom.getpath(res.getparent())

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
            assert entety_1["fonduer_doc_id"] == entety_2["fonduer_doc_id"]
            tabulated.append(
                (
                    entety_1["fonduer_doc_id"],
                    entety_1["text"],
                    entety_1["fd_sentence_id"],
                    entety_1["ls_spot_offsets"][0],
                    entety_1["ls_spot_offsets"][1],
                    entety_2["fonduer_doc_id"],
                    entety_2["text"],
                    entety_2["fd_sentence_id"],
                    entety_2["ls_spot_offsets"][0],
                    entety_2["ls_spot_offsets"][1],
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
            fonduer_doc_id = str(
                session.query(Document.id).filter(Document.name == filename).first()[0]
            )
            tree = self._get_html_tree_from_string(
                annotated_doc["data"]["text"]
            )  # recreate html tree for doc

            for annotations in annotated_doc["annotations"]:
                if not annotations["result"]:
                    continue
                for entety in annotations["result"]:
                    if entety.get("value"):
                        xpath_rel = entety["value"]["start"]
                        xpath_abs = self._get_absolute_xpath(xpath_rel, tree)
                        fd_sentence_id = (
                            session.query(Sentence.id)
                            .filter(
                                Sentence.document_id == fonduer_doc_id,
                                Sentence.xpath == xpath_abs,
                            )
                            .first()
                        )
                        label = entety["value"]["labels"][0]
                        ls_ID = entety["id"]
                        id_label[ls_ID] = label

                        spots[ls_ID] = {
                            # "xpath_rel": xpath_rel,
                            "xpath_abs": xpath_abs,
                            "label": label,
                            "text": entety["value"]["text"].replace("\\n", ""),
                            "ls_ID": ls_ID,
                            "fd_sentence_id": str(fd_sentence_id[0]),
                            "filename": filename,
                            "fonduer_doc_id": fonduer_doc_id,
                            "ls_spot_offsets": (
                                str(entety["value"]["startOffset"]),
                                str(entety["value"]["endOffset"]),
                            ),
                        }
                    else:
                        relations.append(
                            (entety["from_id"], entety["to_id"], entety["labels"])
                        )
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
            str(cand[1].context.char_start),
            str(cand[1].context.char_end + 1),
            str(cand[0].document_id),
            str(cand[0].context.get_span()),
            str(cand[0].context.sentence.id),
            str(cand[0].context.char_start),
            str(cand[0].context.char_end + 1),
        )
        if canddidate_tuple in self.spots_table:
            return 1
        return 0
