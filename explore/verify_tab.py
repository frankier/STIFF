import click
from os.path import join as pjoin

POS_MAP = {"a": "adj", "r": "adv", "n": "noun", "v": "verb"}


def split_line(line):
    if "\t" in line:
        return line.split("\t", maxsplit=1)
    else:
        return line.split("        ", maxsplit=1)


@click.command("verify_tab")
@click.argument("wordnet_dir", type=click.Path(file_okay=False, resolve_path=True))
@click.argument("lang_tabs", type=click.File("r"), nargs=-1)
def verify_tab(wordnet_dir, lang_tabs):
    data_files = {}
    for code, suffix in POS_MAP.items():
        data_files[code] = open(pjoin(wordnet_dir, "data." + suffix), "rb")
    problems = {}
    for lang_tab in lang_tabs:
        problems[lang_tab] = set()
        print(f"Processing {lang_tab.name}")
        for line in lang_tab:

            def add_err(err):
                problems[lang_tab].add(err)
                print(err + f" in {lang_tab.name}:")
                print(line.strip())

            if not line.strip() or line.startswith("#"):
                continue
            ref, _ = split_line(line)
            if "-" not in ref:
                add_err("Badly formatted ref (expected '-')")
                print()
                continue
            offset, pos = ref.split("-")
            offset = int(offset)
            if pos not in data_files:
                if pos == "s":
                    add_err("Uses satellite adjective tag")
                    print()
                    pos = "a"
                else:
                    add_err("Unknown POS tag")
                    print()
                    continue
            data_files[pos].seek(offset - 1)
            char = data_files[pos].read(1)
            if char != b"\n":
                add_err("Unknown offset")
                i = 0
                while 1:
                    i += 1
                    data_files[pos].seek(-2, 1)
                    char = data_files[pos].read(1)
                    if char == b"\n":
                        print(
                            "Should it be {} (moved by {})?".format(
                                data_files[pos].tell(), i
                            )
                        )
                        break
                print()
    print("Summary")
    for lang_tab in lang_tabs:
        if problems[lang_tab]:
            print(f"{lang_tab.name} has the following problems {problems[lang_tab]}")


if __name__ == "__main__":
    verify_tab()
