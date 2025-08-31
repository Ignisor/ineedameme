from typing import Optional
from src.core import TemplateRepository, OpenRouterTemplateMatcher, TemplatePicker


def test_run(description: str, reference_image: Optional[str] = None):
    ref_img = None

    if reference_image:
        with open(reference_image, "rb") as f:
            ref_img = f.read()

    picker = TemplatePicker(
        repo=TemplateRepository(),
        matcher=OpenRouterTemplateMatcher(),
    )

    templates = picker.pick_top_k(situation=description)

    print("\nPicked templates:")
    for t in templates:
        print(t.score, t.template)

    return templates


if __name__ == "__main__":
    # res = test_run("Generate a 'Stonks' meme image but use a face from the reference provided")
    # res = test_run(
    #     "I am making a BI interface and have some free spaces with no charts, I want to put some meme there instead of a chart with the face of my client in it. Something representing success."
    # )
    res = test_run("friend insists tabs are superior in code review")
    # res = test_run(
    #     "Make a meme to add to this converstaion: \n"
    #     "  Friend: Hey bro, I'm going to the party tomorrow night, you should come with me. \n"
    #     "  Me: I can't, I have to work :( \n"
    #     "  Friend: But it's gonna be fun, you should come with me. \n"
    # )
    # res = test_run(
    #     "Make a meme to add to this converstaion: \n"
    #     "  Friend: Hey bro, what are you doing rn? \n"
    #     "  Me: I'm taking a shit bro. \n"
    #     "  Friend: Have a good shit bro. \n"
    #     "  Me: Love u bro <3 \n"
    # )
