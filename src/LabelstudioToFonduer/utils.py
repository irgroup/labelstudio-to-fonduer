import os
import shutil

import label_studio_sdk
from fonduer.candidates import MentionNgrams


def resolve_relations(relations, id_label):
    resolved = []
    for relation in relations:
        resolved.append((id_label.get(relation[0]), id_label.get(relation[1])))
    return set(resolved)


def determine_ngram_size(export, label):
    lengths = []
    for doc in export:
        for spot in doc["spots"]:
            if spot["label"] == label:
                lengths.append(len(spot.get("text").split(" ")))
    return MentionNgrams(n_max=max(lengths), n_min=min(lengths))


BASE_TEMPLATE = """
        <View>
        <Relations>
            <Relation value="org:founded_by"/>
            <Relation value="org:founded"/>
        </Relations>
        <Labels name="label" toName="text">
            
            
            
        <Label value="Location" background="#FFA39E"/><Label value="Job" background="#04c317"/></Labels>

        <HyperText name="text" value="$text" valueType="url"/>
        </View>
        """


def create_ls_project(
    label_studio_connection: label_studio_sdk.client.Client,
    project_name: str,
    template: str = BASE_TEMPLATE,
) -> label_studio_sdk.project.Project:
    """Create an entity labeling project in label-studio with a provided name and template.

    Args:
        label_studio_connection (label_studio_sdk.client.Client): Label-Studio connection from the SDK.
        project_name (str): Name of the project to create.
        template (str, optional): A basic template to provide initial information that can be changed in the UI. Defaults to BASE_TEMPLATE.

    Returns:
        label_studio_sdk.project.Project: The Label-Studio SDK project object that was created.
    """
    assert label_studio_connection.check_connection().get("status") == "UP"
    project = label_studio_connection.start_project(
        title=project_name, label_config=template
    )
    return project


def get_project_by_name(
    project_name: str, label_studio_connection: label_studio_sdk.client.Client
) -> label_studio_sdk.project.Project:
    """Retrieve a Label-Studio project by its name.

    Args:
        project_name (str): Name of the project to be retrieved.
        label_studio_connection (label_studio_sdk.client.Client): Label-Studio connection from the SDK.

    Returns:
        label_studio_sdk.project.Project: The Label-Studio SDK project object.
    """
    for project in label_studio_connection.list_projects():
        if project.title == project_name:
            return project


def create_ls_data_dir(ls_base_dir: str, project_name: str) -> str:
    """Create a local directory for the provided project were data can be stored and imported into Label-Studio.

    Args:
        ls_base_dir (str): Base directory for Label-Studio as specified in the `LABEL_STUDIO_BASE_DATA_DIR` environment variable of Label-Studio.
        project_name (str): Name of the project in Label-Studio.

    Returns:
        str: Path to the directory where the data for the project needs to be placed.
    """
    os.mkdir(os.path.join(ls_base_dir, project_name))

    print("Created dir for project", project_name)
    print(
        f"""Please regisrer local storage in LS UI: 
    1. Go to: Projects/{project_name}/Settings/Clud Storage
    2. Select `Add Source Storage`
    3. Choose `Local files` as Storage Type and `{project_name}` as storage title.
    4. Paste `/{os.path.join("label-studio","data", project_name)}` as Absolute local path"""
    )

    return os.path.join(ls_base_dir, project_name)


import shutil


def import_data_to_ls(
    project: label_studio_sdk.project.Project,
    ls_project_dir: str,
    data_dir: str,
    html_data_dir: str,
    recursive: bool = False,
    k: int = 0,
):
    """Import data to label studio (LS) by copying the files to the project dir and also to a html dir for later reference. If recursive is set, files from sub dirs are also included. If a k is specified only the top k files are imported.

    Args:
        project (label_studio_sdk.project.Project): LS project data is imported to.
        ls_project_dir (str): Path to label studio project dir.
        data_dir (str): Path to the data root dir to be imported.
        html_data_dir (str): Path to the HTML dir for referencing.
        recursive (bool, optional): Include sub dirs or not. Defaults to False.
        k (int, optional): Include only the top k files. If k is 0, all files are imported. Defaults to 0.
    """
    early_stop = [True if k > 0 else False]

    def import_to_ls(file_path):
        split = file_path.split(os.sep)
        file_name = split[-1]
        subset_name = split[-2]

        filename_extended = subset_name + "_" + file_name

        shutil.copyfile(file_path, os.path.join(ls_project_dir, filename_extended))
        shutil.copyfile(file_path, os.path.join(html_data_dir, filename_extended))

        project_name = file_path.split(ls_project_dir)[-1]
        print(os.path.join(project_name, filename_extended))
        project.import_tasks(
            [
                {
                    "text": "/data/local-files/?d=/label-studio/"
                    + os.path.join(project_name, filename_extended)
                }
            ]
        )

    def import_dir(dir_to_import):
        c = 0
        for file_name in os.listdir(dir_to_import):
            file_path = os.path.join(dir_to_import, file_name)
            if os.path.isdir(file_path) and recursive:
                import_dir(file_path)

            elif file_name.endswith(".html") or file_name.endswith(".htm"):
                import_to_ls(file_path)
                c += 1
                if c == k and early_stop:
                    break

    import_dir(data_dir)
