from typing import Optional

from src.core import (
    DownloadedImage,
    ImageDownloader,
    ImageEditPromptGenerator,
    MemeImageGenerator,
    OpenRouterTemplateMatcher,
    TemplatePicker,
    TemplateRepository,
)


def test_run(description: str, reference_image: Optional[str] = None):
    ref_img = None

    if reference_image:
        with open(reference_image, "rb") as f:
            ref_img = DownloadedImage(url=reference_image, content=f.read(), mime_type="image/png")

    picker = TemplatePicker(
        repo=TemplateRepository(),
        matcher=OpenRouterTemplateMatcher(),
    )

    templates = picker.pick_top_k(situation=description)

    print("\nPicked templates:")
    for t in templates:
        print(t.score, t.template)

    template = templates[0].template
    template_image = ImageDownloader().download(template.blank)
    prompt = ImageEditPromptGenerator().create_prompt(
        user_description=description,
        template=template,
        template_image=template_image,
        reference_image=ref_img,
    )

    print("\nPrompt:")
    print(prompt)

    res = MemeImageGenerator().generate(
        prompt=prompt,
        template_image=template_image,
        reference_image=ref_img,
    )

    print("\nImage generated!")
    with open("generated_image.png", "wb") as f:
        f.write(res.content)

    return res


if __name__ == "__main__":
    res = test_run(
        "Make a 'Stonks' meme image but use a person from the reference provided", reference_image="rhys.png"
    )
    # res = test_run(
    #     "I am making a BI interface and have some free spaces with no charts, I want to put some meme there instead of a chart with the face of my client in it. Something representing success."
    # )
    # res = test_run("Friend insists tabs are superior in code but I think spaces are better. Be rude about it.")
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
