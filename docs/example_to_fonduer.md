# Transfer labels to Fonduer

In this example, we will transfer the labels we manually annotated in Label Studio to Fonduer to be used as gold labels for evaluation.

???+ danger
    Before any labels are annotated, please ensure that the document representations in Fonduer and Label Studio are the same. Otherwise, the labels might not be transferable! See [example_document_converter](example_document_converter.md) for further information.


## Fonduer setup:
The way fonduer is set up might influence the ability to transfer labels between the systems. Therefore, Fonduer has to be configured so that it does not need to modify the documents.

### Read export
First, we start with reading the export from Label Studio. We can use some of the information from our export to configure our data model in fonduer later.

```Python
from LabelstudioToFonduer.to_fonduer import parse_export

export = parse_export(label_studio_export_path="data/export.json")
```

### Create the fonduer project
After that, we create the project in fonduer:
```Python
from LabelstudioToFonduer.fonduer_tools import save_create_project  # delete old versions of the project
from fonduer import Meta, init_logging

conn_string = "postgresql://postgres:postgres@127.0.0.1:5432/"

save_create_project(conn_string=conn_string, project_name="test")

init_logging(log_dir="logs"))
session = Meta.init(conn_string + "test").Session()
```


### Setup HTML document processor
Fonduer might read the documents with the wrong encoding, which causes errors. To avoid this, a dedicated `HTMLDocPreprocessor` can be used. `LabelStudio_to_Fonduer` provides a slightly modified `HTMLDocPreprocessor` as a starting point named [My_HTMLDocPreprocessor](https://github.com/irgroup/labelstudio-to-fonduer/blob/main/src/LabelstudioToFonduer/document_processor.py). 

The processor can be imported like this:
```Python
from LabelstudioToFonduer.document_processor import My_HTMLDocPreprocessor

doc_preprocessor = My_HTMLDocPreprocessor(document_path, max_docs=10)
```


### Setup lingual parser
By default, Fonduer uses a lingual parser that splits sentences based on the [SpaCy](https://spacy.io/) `split_sentences` function. While this method generally performs quite well, it does not handle abbreviations and special punctuation well.

If our labels contain punctuations or abbreviations, we need to use a modified `lingual_parser`.
`LabelStudio_to_Fonduer` comes with a modified version that splits sentences only on the `.` char and can handle given exceptions. 
To add exceptions and use this `ModifiedSpacyParser`, we can use this code:

```Python
from LabelstudioToFonduer.lingual_parser import ModifiedSpacyParser

exceptions = [".NET", "Sr.", ".WEB", ".de", "Jr.", "Inc.", "Senior."]
my_parser = ModifiedSpacyParser(lang="en", split_exceptions=exceptions)
```


## Import documents
If the pipeline is set up, we can import our documents.
```python
corpus_parser = Parser(
    session, 
    lingual_parser=my_parser, 
    structural=True, 
    lingual=True, flatten=[])
corpus_parser.apply(doc_preprocessor, parallelism=4)
```



## Setup Fonduer datamodel
In this step, the data model is created and then used to create the labeling functions and so on. For further information, please refer to the Fonduer documentation.

As we already have some labeled data, we can derive some starting values to create the Fonduer data model. This configuration is highly dependent on the data we have.


We can get a list of all unique spans from a label in our export:
```Python
export.lable_entitis("label")
```

For example, we can calculate the minimum and maximum ngram size from our export given a label:

```Python
export.ngrams("label")
```

It might be beneficial to test the pipeline in advance to make sure Fonduer does not change any document and all annotated spans can be detected. Therefore, we will not spend too much time in setting up labeling functions and only rudimentarily set up some Fonduer processing for now on. After we ensure that the pipeline works for our data, we will come back to that.


## Load gold label
To use our gold data in fonduer, it is finally time to transfer the labels from Label Studio to Fonduer.

Therefore we create a `converter` entity from `LabelStudioToFonduer` based on our parsed export and the fonduer session.

```Python
from LabelstudioToFonduer.to_fonduer import LabelStudioToFonduer

converter = LabelStudioToFonduer(label_studio_export=export, fonduer_session=session)
```

Then we use the `is_gold` function of our converter as a labeling function in the Fonduer Labeler.


```Python
from fonduer.supervision.models import GoldLabel
from fonduer.supervision import Labeler

labeler = Labeler(session, [TitleDate])

labeler.apply(
    docs=docs,
    lfs=[[converter.is_gold]],
    table=GoldLabel,
    train=True,
    parallelism=PARALLEL,
)
```

To check if we were successful, we can count the transferred labels.

```Python
train_cands = candidate_extractor.get_candidates()
all_gold = labeler.get_gold_labels(train_cands)

golds = []
for k, v in zip(all_gold[0], train_cands[0]):
    if k:
        golds.append(v)
print("Gold labels found:", len(golds))
```


