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


def import_data_to_ls(
    project: label_studio_sdk.project.Project,
    ls_project_dir: str,
    data_dir: str,
    html_data_dir: str,
    recursive: bool = False,
    k: int = 0,
):
    SEPERATOR = os.sep
    early_stop = [True if k > 0 else False]

    def import_dir(directory):
        c = 0
        for file in os.scandir(directory):
            if file.path.endswith(".htm") or file.path.endswith(".html"):
                new_file_name = "_".join(file.path.split(SEPERATOR)[-2:])

                shutil.copyfile(file.path, os.path.join(ls_project_dir, new_file_name))
                shutil.copyfile(file.path, os.path.join(html_data_dir, new_file_name))
                project.import_tasks(
                    [
                        {
                            "text": "/data/local-files/?d=/label-studio/data/"
                            + os.path.join(
                                ls_project_dir.split(SEPERATOR)[-1], new_file_name
                            )
                        }
                    ]
                )
                c += 1
                if c == k and early_stop:
                    break

            elif file.is_dir() and recursive:
                import_dir(file.path)

    import_dir(data_dir)
