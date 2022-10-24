import setuptools

setuptools.setup(
    name="LabelstudioToFonduer",
    version="0.0.1",
    packages=setuptools.find_packages(
        include=["LabelstudioToFonduer", "LabelstudioToFonduer.*"]
    ),
    python_requires=">=3.7",
)
