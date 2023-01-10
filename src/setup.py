import setuptools

setuptools.setup(
    name="LabelstudioToFonduer",
    author="Jüri Keller",
    author_email='jueri.keller@smail.th-koeln.de',
    version="0.2.2",
    packages=setuptools.find_packages(
        include=["LabelstudioToFonduer", "LabelstudioToFonduer.*"]
    ),
    install_requirements=[
        "label_studio_sdk",
        "requests",
        "bs4",
        "fonduer",
        "sqlalchemy",
        "spacy",
        "lxml",
        "pandas",
    ],
    python_requires=">=3.7",
)
