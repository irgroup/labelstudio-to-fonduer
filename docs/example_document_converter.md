In this example, we will prepare our documents before we can use them interchangeably between Label Studio and Fonduer. 

As initially described in the [Introduction](index.md), Fonduer and Label Studio may create their own representations of the documents. This behavior is not desirable if we want to interchange our documents between the two systems.

To avoid this behavior, we will convert our documents and modify the system so that Fonduer does not have to change them.

To convert the documents, run:

```Python
from LabelstudioToFonduer.document_converter import DocumentConverter

documents_path = "my/test/documents/folder"
output_path = "converted/documents/folder"

converter = DocumentConverter()

converter.convert(
    input_=documents_path, 
    output_path=output_path)
```

## Validate conversion:

To check if the documents were converted successfully and are not further changed by Label Studio or Fonduer you can use the [`ConversionChecker`](ConversionChecker).

???+ warning

    Keep in mind that your fonduer pipeline and especially the `lingual_parser` and `HTMLDocPreprocessor` might also influence the results. Probably, this validator needs to be adapted to your needs.

The validator can be run like this:
```Python
from LabelstudioToFonduer.document_converter import ConversionChecker

documents_path = "my/test/documents/folder"

converter = ConversionChecker(
        label_studio_url="",
        label_studio_api_key="",
        fonduer_postgres_url="",
        project_name="my_project"
        )

converter.check(docs_path=documents_path)
```