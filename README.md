# Label Studio to Fonduer
Label Studio to Fonduer is a small library to transfer annotations between [Label Studio](https://labelstud.io/) and [Fonduer](https://github.com/HazyResearch/fonduer).
By that, documents annotated in Label Studio can be used as gold labels in Fonduer and vice versa annotations made in Fonduer can easily be accessed by humans in Label Studio.


Label Studio and especially Fonduer create their own representation of an HTML document. 
![Problem](docs/problem.png | width=300)

Therefore, the documents need to be converted into a structure that does not need to be modified by Label Studio or Fonduer.

![Solution](docs/solution.png | width=300)




## Installation:

```Bash
pip install git+https://github.com/irgroup/labelstudio-to-fonduer.git#egg=labelstudiotofonduer\&subdirectory=src
```



## Examples:
[From Fonduer to Label Studio](docs/ToLabelStudio.ipynb):
```Python
train_cands = candidate_extractor.get_candidates()

converter.create_export(candidates=train_cands, fonduer_export_path="import.json")
```

[From Label Studio to Fonduer](docs/ToFonduer.ipynb):
```Python
converter = ToFonduer(label_studio_export=export, fonduer_session=session)

labeler.apply(
    docs=docs,
    lfs=[[converter.is_gold]],
    table=GoldLabel,
)
```
