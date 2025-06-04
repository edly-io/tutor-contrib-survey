import os
from glob import glob

import click
import importlib_resources
from tutor import hooks

from tutormfe.hooks import PLUGIN_SLOTS, MFE_APPS

from .__about__ import __version__


########################################
# CONFIGURATION
########################################

hooks.Filters.MOUNTED_DIRECTORIES.add_item(("openedx", "survey_api"))

hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        # Add your new settings that have default values here.
        # Each new setting is a pair: (setting_name, default_value).
        # Prefix your setting names with 'SURVEY_'.
        ("SURVEY_VERSION", __version__),
    ]
)

hooks.Filters.CONFIG_UNIQUE.add_items(
    [
        
    ]
)

hooks.Filters.CONFIG_OVERRIDES.add_items(
    [
        
    ]
)


########################################
# INITIALIZATION TASKS
########################################

# To add a custom initialization task, create a bash script template under:
# tutorsurvey/templates/survey/tasks/
# and then add it to the MY_INIT_TASKS list. Each task is in the format:
# ("<service>", ("<path>", "<to>", "<script>", "<template>"))
MY_INIT_TASKS: list[tuple[str, tuple[str, ...]]] = [
    # For example, to add LMS initialization steps, you could add the script template at:
    # tutorsurvey/templates/survey/tasks/lms/init.sh
    # And then add the line:
    ### ("lms", ("survey", "tasks", "lms", "init.sh")),
]


# For each task added to MY_INIT_TASKS, we load the task template
# and add it to the CLI_DO_INIT_TASKS filter, which tells Tutor to
# run it as part of the `init` job.
for service, template_path in MY_INIT_TASKS:
    full_path: str = str(
        importlib_resources.files("tutorsurvey")
        / os.path.join("templates", *template_path)
    )
    with open(full_path, encoding="utf-8") as init_task_file:
        init_task: str = init_task_file.read()
    hooks.Filters.CLI_DO_INIT_TASKS.add_item((service, init_task))


# Images to be built by `tutor images build`.
# Each item is a quadruple in the form:
#     ("<tutor_image_name>", ("path", "to", "build", "dir"), "<docker_image_tag>", "<build_args>")
hooks.Filters.IMAGES_BUILD.add_items(
    [

    ]
)


# Images to be pulled as part of `tutor images pull`.
# Each item is a pair in the form:
#     ("<tutor_image_name>", "<docker_image_tag>")
hooks.Filters.IMAGES_PULL.add_items(
    [
        
    ]
)


# Images to be pushed as part of `tutor images push`.
# Each item is a pair in the form:
#     ("<tutor_image_name>", "<docker_image_tag>")
hooks.Filters.IMAGES_PUSH.add_items(
    [
        
    ]
)

hooks.Filters.ENV_TEMPLATE_ROOTS.add_items(
    # Root paths for template files, relative to the project root.
    [
        str(importlib_resources.files("tutorsurvey") / "templates"),
    ]
)

hooks.Filters.ENV_TEMPLATE_TARGETS.add_items(
    # For each pair (source_path, destination_path):
    # templates at ``source_path`` (relative to your ENV_TEMPLATE_ROOTS) will be
    # rendered to ``source_path/destination_path`` (relative to your Tutor environment).
    # For example, ``tutorsurvey/templates/survey/build``
    # will be rendered to ``$(tutor config printroot)/env/plugins/survey/build``.
    [
        ("survey/build", "plugins"),
        ("survey/apps", "plugins"),
    ],
)


# For each file in tutorsurvey/patches,
# apply a patch based on the file's name and contents.
for path in glob(str(importlib_resources.files("tutorsurvey") / "patches" / "*")):
    with open(path, encoding="utf-8") as patch_file:
        hooks.Filters.ENV_PATCHES.add_item((os.path.basename(path), patch_file.read()))


PLUGIN_SLOTS.add_item((
    "all",
    "desktop_main_menu_slot",
    """
        {
            op: PLUGIN_OPERATIONS.Insert,
            widget: {
                id: 'custom_header',
                type: DIRECT_PLUGIN,
                RenderWidget: () => <CenteredPopup />
            }
        }
    """
))


@MFE_APPS.add()
def _add_my_mfe(mfes):
    mfes["survey"] = {
        "repository": "https://github.com/edly-io/frontend-app-survey.git",
        "port": 2011,
        "version": "master", 
    }
    return mfes