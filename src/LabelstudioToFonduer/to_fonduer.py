# -*- coding: utf-8 -*-
"""Convert Label Studio annotations to Fonduer Annotations.
"""
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import lxml
import pandas as pd
import sqlalchemy
from fonduer.parser.models import Document, Sentence

from .util import init_logger

logger = init_logger(__name__)

# Data model
class LabelStudioEntity:
    """Representation of a Label Studio entity from a document of an export.

    This object represents an entity with all relevant information from a Label Studio Export.

    Args:
        start_offset (int): The number of the first char of the entity in the full sentence.
        end_offset (int): The number of the last char of the entity in the full sentence.
        text (str): The literal text of the entity.
        label (str): The assigned label of the entity.
        xpath (str): The XPath address of the element (full sentence) in the HTML document.
        filename (str): The file name of the document the entities originate from.
        ls_id (str): Label Studio ID.
    """
    def __init__(
        self,
        start_offset: int,
        end_offset: int,
        text: str,
        label: str,
        xpath: str,
        filename: str,
        ls_id,
    ) -> None:
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.text = text
        self.label = label
        self.xpath = xpath
        self.filename = filename
        self.ls_id = ls_id

    def __str__(self) -> str:
        return f"Label-Studio entitie: Start offset: {self.start_offset}, End Offset: {self.end_offset}, Text: {self.text}, Label: {self.label}, XPath: {self.xpath}, Filename: {self.filename}"

    def __repr__(self) -> str:
        return f"<Entitie: start_offset: {self.start_offset}, end_offset: {self.end_offset}, text: {self.text}, label: {self.label}, xpath: {self.xpath}, filename: {self.filename}"


class LabelStudioRelation:
    """Representation of a Label Studio relation between two entities.

    This object represents a relation between the entities with all relevant information. 

    Args:
        from_entity (LabelStudioEntity): The entity the relation is outgoing from.
        to_entity (LabelStudioEntity): The entity the relation is going to.
        direction (str): The direction of the relation.
    """
    def __init__(self, from_entity: LabelStudioEntity, to_entity: LabelStudioEntity, direction: str) -> None:
        self.from_entity = from_entity
        self.to_entity = to_entity
        self.direction = direction


class LabelStudioDocument:
    """Representation of a Label Studio document.

    This object represents a single document in an export from Label Studio. It contains the
    different annotated entities.

    Args:
        filename (str): File name of the document.
        entities (List[LabelStudioEntity]): List of all entities in that document.
        html (str): Original HTML string of the document.
        relations (List[LabelStudioRelation]): List of all relations in that document.
    """
    def __init__(self, filename: str, entities: List[LabelStudioEntity], html: str, relations: List[LabelStudioRelation]) -> None:
        self.filename = filename
        self.entities = entities
        self.html = html
        self.relations = relations

    def __str__(self) -> str:
        return f"Label-Studio Document: File name: '{self.filename}' number entities: {len(self.entities)}."

    def __repr__(self) -> str:
        return f"<Document: filename: {self.filename}, num_entities: {len(self.entities)}>"


class LabelStudioExport:
    """Representation of a Label Studio export.

    This object contains all necessary information from a label studio export to transfer the
    labeled entities to the Fonduer data model. Additionally, supplementing functions to
    determine the set of labels and their ngram size are available.

    Args:
        documents (List[LabelStudioDocument]): Parsed documents that are labeled in the Label
        Studio export.
        file_path (str): Path to the `export.json` file from Label Studio.
    """
    def __init__(self, documents: List[LabelStudioDocument], file_path: str) -> None:
        self.documents = documents
        self.file_path = file_path

    def label(self) -> Set[str]:
        """Get a set of all labels that were assigned in Label Studio.

        Returns:
            Set[str]: Set off all different labels in the export.
        """
        labels = set()
        for document in self.documents:
            for entity in document.entities:
                labels.add(entity.label)
        return labels

    def ngrams(self, label: str) -> Tuple[int, int]:
        """Determine the ngarm size of a label.

        All entities in all documents are split on whitespaces. The length of the shortest and
        longest entity is reported as ngram size.

        ???+ warning "Extra padding needed"

            Fonduer might split sentences differently. Therefore, special characters not
            labeled might also count as tokens. Therefore, a slightly longer ngram size might be
            needed to account for these tokens.

        Args:
            label (str): The label the ngram size should be determined for.

        Returns:
            Tuple[int, int]: A tuple of the minimal and maximal ngram size.
        """
        lengths = set()
        for document in self.documents:
            for entity in document.entities:
                if entity.label == label:
                    lengths.add(len(entity.text.split(" ")))
        return (min(lengths), max(lengths))

    def lable_entitis(self, label: str) -> Set[str]:
        """Get a list of all entities for a given label.

        A set of entity texts from all entities with the given label is created from all documents.

        Args:
            label (str): The label the list of entities texts should be created for.

        Returns:
            Set[str]: List of all entity texts for that label.
        """
        labels_entitis = set()
        for document in self.documents:
            for entity in document.entities:
                if entity.label == label:
                    labels_entitis.add(entity.text)
        return labels_entitis

    def __str__(self) -> str:
        return f"Label-Studio Export from '{self.file_path}' with {len(self.documents)} documents."

    def __repr__(self) -> str:
        return f"<Export filename: {self.file_path}, num_documents: {len(self.documents)}>"


# Export parser into class
def parse_export(label_studio_export_path: str) -> LabelStudioExport:
    """Parse a Label Studio export JSON file into an Export object. The parser extracts documents
    and entities and the relevant features to match label studio annotations with fonduer
    annotations.

    Args:
        label_studio_export_path (str): Path to the export.json file exported from label studio.

    Returns:
        LabelStudioExport: Export object with all necessary information at hand.
    """
    with open(label_studio_export_path, "r") as file:
        export = json.load(file)

    documents = []
    for task in export:
        # get html key, may be different in the label-studio annotation view
        html_key = list(task["data"].keys())[0]
        html_string = task["data"][html_key]

        # get filename
        filename = "-".join(task["file_upload"].split("-")[1:])

        if task["annotations"]:
            for entities in task["annotations"]:
                entities_list = entities["result"]

                entities = []
                relations = []
                for entity in entities_list:
                    # entity is relation
                    if not entity.get("value"):
                        relations.append(entity)
                    else:
                        # entity is entity
                        # offset
                        start_offset = entity["value"]["startOffset"]
                        end_offset = entity["value"]["endOffset"]

                        # text
                        text = entity["value"]["text"]
                        label = entity["value"]["hypertextlabels"][0]

                        # Check for whitespaces in the labeling and adjust the offset accordingly
                        # Whitespaces will be striped later
                        if text.startswith(" "):
                            start_offset += 1
                        if text.endswith(" "):
                            end_offset -= 1
                        # Label Studio ID
                        ls_id = entity["id"]

                        # XPath
                        xpath = entity["value"]["start"]
                        entity_parsed = LabelStudioEntity(start_offset, end_offset, text.strip(), label, xpath, filename, ls_id)
                        entities.append(entity_parsed)
                
                # Resolve relations
                # If only two entoties and no relations parsed
                if (not relations and len(entities) == 2):
                    relation_parsed = LabelStudioRelation(entities[0], entities[1], "")
                    document = LabelStudioDocument(filename=filename, entities=entities, html=html_string, relations=[relation_parsed])
                else:
                    relations_parsed = []
                    for relation in relations:
                        # Get the entities
                        entity1 = None
                        entity2 = None
                        for entity in entities:
                            if entity.ls_id == relation["from_id"]:
                                entity1 = entity
                            if entity.ls_id == relation["to_id"]:
                                entity2 = entity
                        # Get the relation direction
                        direction = relation["direction"]
                        relations_parsed.append(LabelStudioRelation(entity1, entity2, direction))

                    document = LabelStudioDocument(filename=filename, entities=entities, html=html_string, relations=relations_parsed)
                documents.append(document)
    return LabelStudioExport(documents=documents, file_path=label_studio_export_path)


# API class
class ToFonduer:
    """Interface to transfer Label Studio labels to Fonduer.

    Provided with a parsed label studio export and a connection to Fonduer, this interface can
    transfer labels from the Label Studio Export to Fonduer. Therefore, the annotated entities
    from the Label Studio export are used to identify Candidates in Fonduer.
    As this transfer is not trivial, multiple features are needed:

    - Filename: Identifies the document
    - XPath: Identifies the sentence (element) in the document.
    - Offsets: Identify the beginning and end of the actual labeled text in the sentence.

    Fonduer uses an absolut XPath and Label Studio a relative XPath. Therefore, the relative
    XPath is transferred to a relative one by using the original HTML.

    From all identified entities, a table is created that can be used by a Fonduer gold function
    to compare Fonduer candidates to the table. If a Fonduer Candidate is in the gold table, it
    is a gold label.

    Args:
        label_studio_export (LabelStudioExport): The parsed Label Studio export.
        fonduer_session (sqlalchemy.orm.session.Session): The connection to Fonduer.
    """
    def __init__(
        self,
        label_studio_export: LabelStudioExport,
        fonduer_session: sqlalchemy.orm.session.Session,
    ) -> None:
        self.label_studio_export = label_studio_export
        self.fonduer_session = fonduer_session

        self.gold_table = self.make_gold_table()

    # determine entities in FD
    def fonduer_document_id(self, entity: LabelStudioEntity) -> Union[int, bool]:
        """Get the Fonduer document ID from a label studio entity. To find the correct entity
        the filename is queried in the Fonduer database.

        Args:
            entity (LabelStudioEntity): The label studio entity for that the fonduer document
                                        id should be retrieved.

        Returns:
            Union[int, bool]: Fonduer document id or False if no id could be retrieved.
        """
        document_id = (
            self.fonduer_session.query(Document.stable_id)
            .filter(
                Document.name == entity.filename[:-5],
            )
            .all()
        )
        if len(document_id) > 1:
            logger.warning(f"Doc: '{entity.filename}' Document ID: '{document_id}' is not unique.")
            return False
        elif len(document_id) == 0:
            logger.warning(f"Doc: '{entity.filename}' Document ID: '{document_id}' not found.")
            return False
        else:
            return document_id[0][0]

    def fonduer_sentence_id(
        self, entity: LabelStudioEntity, document_id: int, html: str
    ) -> Optional[int]:
        """Get the Fonduer sentence ID from a label studio entity, its document ID and the original
        html.
        To find the correct ID, the relative Label Studio XPath is converted into an absolute one
        which is then used to query the Fonduer database together with the document ID

        Args:
            entity (LabelStudioEntity): The label studio entity for that the fonduer document
                                        id should be retrieved.
            document_id (int): Fonduer ID for the document the entity originates from.
            html (str): Original HTML document as a string.

        Returns:
            Optional[int]: Fonduer sentence ID or None if no sentence ID could be retrieved.
        """

        def get_absolute_xpath(relative_xpath: str, dom: lxml.etree.ElementTree) -> Optional[str]:
            """Retrieve an absolute XPath as fonduer uses in its database from a relative XPath.
            The relative XPath is searched in the `dom`. Further, all html[1] elements are simplified
            into plain html elements in the xpath.

            Args:
                relative_xpath (str): Relative XPath to be absolutized.
                dom (lxml.etree.ElementTree): Dom of the html the relative XPath originates from.

            Returns:
                Optional[str]: Absolut XPath or None if no XPath could be retrieved.
            """
            results = dom.xpath("/" + relative_xpath)
            if not results:
                return None
            else:
                results = results[0]

            element = results.getparent()
            if element.tail:
                element = element.getparent()
            absolute_xpath = dom.getpath(element)
            absolute_xpath = absolute_xpath.replace("html[1]", "html")

            # if absolute_xpath.endswith("/span"):
            #     absolute_xpath = absolute_xpath[:-5]
            return absolute_xpath

        # Create dom
        dom = lxml.etree.ElementTree(lxml.html.fromstring(html))

        xpath = entity.xpath

        # convert xpath
        absolute_xpath = get_absolute_xpath(xpath, dom)

        # handle results
        if not absolute_xpath:
            # try again without tbody elements, Label Studio might add them.
            xpath = re.sub(r"tbody\[\d\]/", r"", entity.xpath)
            absolute_xpath = get_absolute_xpath(xpath, dom)
            if not absolute_xpath:
                document_name = (
                    self.fonduer_session.query(Document.name)
                    .filter(Document.stable_id == document_id)
                    .first()[0]
                )
                logger.warning(
                    f"Doc: '{document_name}' Fonduer Doc ID: '{document_id}': absolute XPath could not retrieved."
                )
                return None

        document_id_loose = (
            self.fonduer_session.query(Document.id)
            .filter(Document.stable_id == document_id)
            .first()[0]
        )
        candidates = (
            self.fonduer_session.query(Sentence.id)
            .filter(
                Sentence.document_id == document_id_loose,
                Sentence.xpath == absolute_xpath,
                Sentence.text.contains(entity.text),
            )
            .all()
        )
        if not candidates:
            document_name = (
                self.fonduer_session.query(Document.name)
                .filter(Document.stable_id == document_id)
                .first()[0]
            )
            logger.warning(
                f"Doc: '{document_name}': No candidates found in Database that match: XPath: '{absolute_xpath}', Text: '{entity.text}', Fonuer Document ID: '{document_id_loose}'."
            )
            return None
        elif len(candidates) > 1:
            logger.warning(f"Doc: '{document_name}': Multiple candidates found.")
            return None
        else:
            # Offset start, offset stop, sentence id
            return candidates[0][0]

    # Create gold table
    def make_gold_table(self) -> List[Dict[str, Dict[str, Any]]]:
        """Create a table with all necessary information (features) to relate a Fonduer candidate
        relation to a relation annotated in label studio.

        Returns:
            List[Dict[str, Dict[str, Any]]]: List of Lists with all features for a relation between
            two entities in one row.
        """

        def get_features(entity: LabelStudioEntity) -> Dict[str, Any]:
            document_id = self.fonduer_document_id(entity)
            sentence_id = self.fonduer_sentence_id(entity, document_id, document.html)
            return {
                "document_id": document_id,
                "offset_start": entity.start_offset,
                "offset_stop": entity.end_offset,
                "sentence_id": sentence_id,
                "text": entity.text,
            }

        gold_table = []
        label = self.label_studio_export.label()

        assert len(label) == 2

        for document in self.label_studio_export.documents:
            # Create entity dict
            for relation in document.relations:
                features = {}
                features_from = get_features(relation.from_entity)
                features_to = get_features(relation.to_entity)

                if not (all(features_from) and all(features_to)):
                    logger.warning(
                        f"Doc:  '{document.filename}': Skipping entity, not all features set."
                    )
                    continue
                else:
                    features[relation.from_entity.label.lower()] = features_from
                    features[relation.to_entity.label.lower()] = features_to

                if (
                    features[list(features.keys())[0]]["document_id"]
                    == features[list(features.keys())[1]]["document_id"]
                ):
                    gold_table.append(features)
                else:
                    logger.warning(
                        f"Doc: '{document.filename}': Feature document IDs not matching."
                    )

        return gold_table

    # Create gold function
    def is_gold(self, cand):
        """Check if a provided candidate is gold labeled entity.
        Args:
            cand (fonduer.candidates.models.Candidate): A fonduer candidate to be checked.
        Returns:
            int: 1 if the candidate is gold labeled, 0 if not.
        """
        # Offsets are adapted to label studio offsets

        features = {}
        for entity in cand:
            feature = {
                "document_id": entity.document.stable_id,
                "offset_start": entity.context.char_start + 1,
                "offset_stop": entity.context.char_end + 2,
                "sentence_id": entity.context.sentence.id,
                "text": entity.context.get_span(),
            }
            features[entity.type] = feature

        if features in self.gold_table:
            return 1
        else:
            return 0

    def export_table(
        self, candidates: List[Any] = None, filename: str = ""
    ) -> Union[str, pd.DataFrame]:
        """Export the gold table to a DataFrame or CSV for further analysis.

        Args:
            candidates (List[Any], optional): Fonduer candidates. Defaults to None.
            filename (str, optional): Path to export the table too. Defaults to "" if not set only
            the pandas table is returned.

        Returns:
            Union[str, pd.DataFrame]: Path to the export csv or the Pandas Data Frame itself.
        """

        def serialize(candidate: List[Any]) -> Dict[str, Any]:
            """Serialize a Fonduer candidates object into a Dictionary with the relevant fields.

            Args:
                candidate (List[Any]): Fonduer Candidates object.

            Returns:
                Dict[str, Any]: Dictionary with serialized info.
            """
            features = {}
            for entity in candidate:
                feature = {
                    "document_id": entity.document.stable_id,
                    "offset_start": entity.context.char_start + 1,
                    "offset_stop": entity.context.char_end + 2,
                    "sentence_id": entity.context.sentence.id,
                    "text": entity.context.get_span(),
                }
                features[entity.type] = feature
            return features

        def flattend_dict(full_dict: Dict[str, Any]) -> Dict[str, Any]:
            """Flatten a dictionary of multiple entities into flat dictionary.

            Args:
                full_dict (Dict[str, Any]): Deep dictionary with multiple sub-dictionaries.

            Returns:
                Dict[str, Any]: Flattened dictionary.
            """
            new_dict = {}
            for key in full_dict:
                sub_dict = full_dict[key]
                for k, v in sub_dict.items():
                    new_dict[key + "_" + k] = v
            return new_dict

        table = []
        if candidates:
            for candidate in candidates[0]:
                flattened = flattend_dict(serialize(candidate))
                flattened["label"] = "cand"
                table.append(flattened)

        for row in self.gold_table:
            flattened = flattend_dict(row)
            flattened["label"] = "gold"
            table.append(flattened)

        pd_table = pd.DataFrame(table)

        if filename:
            pd_table.to_csv(filename, index=False)
            return filename
        else:
            return pd_table
