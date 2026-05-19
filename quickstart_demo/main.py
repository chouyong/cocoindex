"""CocoIndex app template."""
import pathlib
from typing import Iterator

import cocoindex as coco


@coco.lifespan
def coco_lifespan(builder: coco.EnvironmentBuilder) -> Iterator[None]:
    """Configure the CocoIndex environment."""
    builder.settings.db_path = pathlib.Path("./cocoindex.db")
    yield


@coco.fn
async def app_main() -> None:
    """Define your main pipeline here.

    Common pattern:
      1) Declare targets/target states under stable 'setup/...' paths.
      2) Enumerate inputs (files, DB rows, etc.).
      3) Mount per input processing unit using a stable path.

    Note: app_main can accept parameters (e.g., sourcedir/outdir) passed via coco.App(...)
    """

    # 1) Declare targets/target states
    # Example (local filesystem):
    #   target = await coco.use_mount(
    #       coco.component_subpath("setup"),
    #       localfs.declare_dir_target,
    #       outdir,
    #   )

    # 2) Enumerate inputs
    # Example (walk a directory):
    #   files = localfs.walk_dir(
    #       sourcedir,
    #       path_matcher=PatternFilePathMatcher(included_patterns=["**/*.pdf"]),
    #   )

    # 3) Mount a processing unit for each input under a stable path
    # Example:
    #   for f in files:
    #       await coco.mount(
    #           coco.component_subpath("process", str(f.relative_path)),
    #           process_file_function,
    #           f,
    #           target,
    #       )

    pass


app = coco.App(
    coco.AppConfig(name="quickstart_demo"),
    app_main,
)
