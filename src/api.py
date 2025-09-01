from __future__ import annotations

import os
from dataclasses import dataclass
import logging
import uuid
from pathlib import Path
import sys
from typing import Optional, List

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import random

from src.core import (
    DownloadedImage,
    GeneratedImage,
    ImageDownloader,
    ImageEditPromptGenerator,
    MemeImageGenerator,
    OpenRouterTemplateMatcher,
    TemplatePicker,
    TemplateRepository,
    SafetyRefusalError,
)


@dataclass(frozen=True)
class MemeResult:
    image: GeneratedImage
    template_id: str
    template_name: str
    prompt: str


class MemeService:
    _picker: TemplatePicker
    _downloader: ImageDownloader
    _prompt_gen: ImageEditPromptGenerator
    _image_gen: MemeImageGenerator
    _logger: logging.Logger

    def __init__(self) -> None:
        self._picker = TemplatePicker(repo=TemplateRepository(), matcher=OpenRouterTemplateMatcher())
        self._downloader = ImageDownloader()
        self._prompt_gen = ImageEditPromptGenerator()
        self._image_gen = MemeImageGenerator()
        self._logger = logging.getLogger("ai.memegen")
        # Ensure logs appear in uvicorn terminal even if root level is higher
        if not self._logger.handlers:
            handler = logging.StreamHandler(stream=sys.stdout)
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

    def generate_meme(
        self,
        description: str,
        reference_file: Optional[UploadFile] = None,
        reference_url: Optional[str] = None,
    ) -> MemeResult:
        description = (description or "").strip()
        cid = str(uuid.uuid4())
        self._logger.info(
            f"cid={cid} step=start description_len={len(description)}"
            f" has_ref_url={bool(reference_url and reference_url.strip())}"
            f" has_ref_file={bool(reference_file and (reference_file.filename or '').strip())}"
        )
        if not description:
            raise HTTPException(status_code=400, detail="Description is required")

        # Retry template picking once
        top = None
        for attempt in range(2):
            try:
                self._logger.info(f"cid={cid} step=pick_template attempt={attempt + 1} situation={description!r}")
                top = self._picker.pick_best(situation=description)
                if top is not None:
                    self._logger.info(
                        f"cid={cid} step=pick_template_success template_id={top.template.id}"
                        f" template_name={top.template.name!r} score={getattr(top, 'score', 0.0):.3f}"
                        f" blank_url={top.template.blank}"
                    )
                    break
                if attempt == 1:
                    raise HTTPException(status_code=500, detail="Failed to select a template")
            except Exception as e:
                self._logger.warning(f"cid={cid} step=pick_template_error attempt={attempt + 1} error={e!r}")
                if attempt == 1:
                    raise HTTPException(status_code=500, detail=f"Failed to select a template: {e}")
                continue
        if top is None:
            raise HTTPException(status_code=500, detail="Failed to select a template")

        template = top.template
        self._logger.info(f"cid={cid} step=download_template_image url={template.blank}")
        template_image = self._downloader.download(template.blank)
        self._logger.info(
            f"cid={cid} step=template_image_ready mime={template_image.mime_type} size={len(template_image.content)}"
        )

        if reference_file is not None:
            self._logger.info(
                f"cid={cid} step=reference_upload_received filename={reference_file.filename!r}"
                f" content_type={reference_file.content_type!r}"
            )
        if reference_url is not None and reference_url.strip():
            self._logger.info(f"cid={cid} step=reference_url_received url={reference_url.strip()}")
        ref_img = self._build_reference_image(reference_file=reference_file, reference_url=reference_url)
        if ref_img is not None:
            self._logger.info(
                f"cid={cid} step=reference_image_ready mime={ref_img.mime_type} size={len(ref_img.content)}"
            )

        # Retry prompt creation once
        prompt = ""
        for attempt in range(2):
            try:
                self._logger.info(
                    f"cid={cid} step=create_prompt attempt={attempt + 1} template_id={template.id}"
                    f" has_template_image=True has_reference_image={bool(ref_img is not None)}"
                )
                prompt = self._prompt_gen.create_prompt(
                    user_description=description,
                    template=template,
                    template_image=template_image,
                    reference_image=ref_img,
                )
                self._logger.info(f"cid={cid} step=create_prompt_success prompt={prompt!r}")
                break
            except Exception as e:
                self._logger.warning(f"cid={cid} step=create_prompt_error attempt={attempt + 1} error={e!r}")
                if attempt == 1:
                    raise HTTPException(status_code=500, detail=f"Failed to create prompt: {e}")
                continue

        # Image generation with safety-aware fallback
        generated: Optional[GeneratedImage] = None
        for attempt in range(2):
            try:
                self._logger.info(
                    f"cid={cid} step=generate_image attempt={attempt + 1}"
                    f" prompt_len={len(prompt)} has_ref_image={bool(ref_img is not None)}"
                )
                generated = self._image_gen.generate(
                    prompt=prompt,
                    template_image=template_image,
                    reference_image=ref_img,
                )
                self._logger.info(
                    f"cid={cid} step=generate_image_success mime={generated.mime_type} size={len(generated.content)}"
                )
                break
            except SafetyRefusalError as e:
                self._logger.warning(f"cid={cid} step=generate_image_refused attempt={attempt + 1} error={e!r}")
                # Safety fallback: regenerate a softened prompt and retry once
                try:
                    self._logger.info(
                        f"cid={cid} step=create_prompt_soft attempt=1 template_id={template.id}"
                        f" has_template_image=True has_reference_image={bool(ref_img is not None)}"
                    )
                    soft_prompt = self._prompt_gen.create_prompt(
                        user_description=description,
                        template=template,
                        template_image=template_image,
                        reference_image=ref_img,
                        safety_soften=True,
                    )
                    self._logger.info(f"cid={cid} step=create_prompt_soft_success prompt={soft_prompt!r}")
                except Exception as e2:
                    self._logger.warning(f"cid={cid} step=create_prompt_soft_error attempt=1 error={e2!r}")
                    # If we fail to create a soft prompt, surface original safety refusal
                    raise e

                try:
                    self._logger.info(
                        f"cid={cid} step=generate_image_soft attempt=1 prompt_len={len(soft_prompt)}"
                        f" has_ref_image={bool(ref_img is not None)}"
                    )
                    generated = self._image_gen.generate(
                        prompt=soft_prompt,
                        template_image=template_image,
                        reference_image=ref_img,
                    )
                    self._logger.info(
                        f"cid={cid} step=generate_image_soft_success mime={generated.mime_type} size={len(generated.content)}"
                    )
                    # Expose the softened prompt in result
                    prompt = soft_prompt
                    break
                except SafetyRefusalError as e_soft:
                    self._logger.warning(f"cid={cid} step=generate_image_soft_refused attempt=1 error={e_soft!r}")
                    raise e_soft
                except Exception as e_soft:
                    self._logger.warning(f"cid={cid} step=generate_image_soft_error attempt=1 error={e_soft!r}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to generate image after safety fallback: {e_soft}",
                    )
            except Exception as e:
                self._logger.warning(f"cid={cid} step=generate_image_error attempt={attempt + 1} error={e!r}")
                if attempt == 1:
                    raise HTTPException(status_code=500, detail=f"Failed to generate image: {e}")
                continue

        if generated is None:
            raise HTTPException(status_code=500, detail="Image generation returned no result")

        return MemeResult(
            image=generated,
            template_id=template.id,
            template_name=template.name,
            prompt=prompt,
        )

    def _build_reference_image(
        self, reference_file: Optional[UploadFile] = None, reference_url: Optional[str] = None
    ) -> Optional[DownloadedImage]:
        if reference_file is not None:
            try:
                filename = (reference_file.filename or "").strip()
                if not filename:
                    return None
                pos = reference_file.file.tell()
                first = reference_file.file.read(1)
                reference_file.file.seek(pos)
                if not first:
                    return None
                return self._build_reference_image_from_upload(reference_file)
            except Exception:
                return None
        if reference_url and reference_url.strip():
            return self._build_reference_image_from_url(reference_url.strip())
        return None

    def _build_reference_image_from_upload(self, file: UploadFile) -> DownloadedImage:
        content = file.file.read()
        mime = file.content_type or "image/png"
        return DownloadedImage(url=file.filename or "upload", content=content, mime_type=mime)

    def _build_reference_image_from_url(self, url: str) -> DownloadedImage:
        return self._downloader.download(url)


app = FastAPI(title="AI MemeGen API", version="0.1.0")
_service = MemeService()

_BASE_DIR = Path(__file__).resolve().parents[1]
_STATIC_DIR = _BASE_DIR / "static"

# Mount /static for any assets (even if we only serve index.html for now)
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.post("/meme")
async def create_meme(
    description: str = Form(...),
    reference_url: Optional[str] = Form(None),
    reference_file: Optional[UploadFile] = File(None),
):
    try:
        result = _service.generate_meme(
            description=description, reference_file=reference_file, reference_url=reference_url
        )
        payload = {
            "mime_type": result.image.mime_type,
            "data_uri": result.image.as_data_uri(),
            "template_id": result.template_id,
            "template_name": result.template_name,
        }
        return JSONResponse(content=payload)
    except HTTPException:
        raise
    except SafetyRefusalError as e:
        raise HTTPException(status_code=400, detail=f"Stupid AI refused to generate the image: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def index() -> FileResponse:
    index_path = _STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(str(index_path))


@app.get("/memes/background")
async def get_background_memes(count: int = 60) -> JSONResponse:
    """Return a list of random meme template image URLs for background tiles."""
    try:
        repo = TemplateRepository()
        candidates = [t.blank for t in repo.all_unique() if t.blank]
        if not candidates:
            return JSONResponse(content={"images": []})
        k = max(0, min(int(count), len(candidates)))
        # If k == len(candidates), sample returns a permuted copy; otherwise random sample
        images: List[str] = random.sample(candidates, k)
        return JSONResponse(content={"images": images})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.api:app", host="0.0.0.0", port=port, reload=True)
