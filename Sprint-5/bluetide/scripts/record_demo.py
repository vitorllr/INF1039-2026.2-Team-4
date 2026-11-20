"""Record the deterministic Pedro usability journey with the real app."""

import os
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


BASE_URL = os.getenv("BLUETIDE_DEMO_URL", "http://127.0.0.1:8765")
PROJECT_DIR = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = PROJECT_DIR / "artifacts"
RAW_VIDEO = ARTIFACT_DIR / "bluetide-pedro-demo.webm"
FINAL_VIDEO = ARTIFACT_DIR / "bluetide-pedro-demo.mp4"


def caption(page: Page, text: str) -> None:
    page.evaluate(
        """
        (text) => {
            document.querySelector('#demo-caption')?.remove();
            const caption = document.createElement('div');
            caption.id = 'demo-caption';
            caption.textContent = text;
            Object.assign(caption.style, {
                position: 'fixed',
                left: '50%',
                bottom: '24px',
                zIndex: '9999',
                maxWidth: '860px',
                padding: '14px 22px',
                border: '1px solid rgba(255,255,255,.22)',
                borderRadius: '14px',
                color: '#fff',
                background: 'rgba(6,43,66,.94)',
                boxShadow: '0 18px 48px rgba(6,43,66,.32)',
                font: '600 18px/1.4 Inter, sans-serif',
                textAlign: 'center',
                transform: 'translateX(-50%)',
            });
            document.body.appendChild(caption);
        }
        """,
        text,
    )


def pause(page: Page, milliseconds: int = 2600) -> None:
    page.wait_for_timeout(milliseconds)


def record() -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    for path in (RAW_VIDEO, FINAL_VIDEO):
        path.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(prefix="bluetide-recording-") as recording_dir:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                record_video_dir=recording_dir,
                record_video_size={"width": 1280, "height": 720},
                color_scheme="light",
            )
            page = context.new_page()
            page.goto(f"{BASE_URL}/web/", wait_until="networkidle")
            caption(page, "Pedro, 23 anos, quer comparar pontos de Ipanema antes de sair para um banho tranquilo.")
            pause(page, 3200)

            page.locator(".coast-map").scroll_into_view_if_needed()
            caption(page, "O mapa mostra quais pontos podem ser comparados e quais ainda não têm dados mínimos.")
            pause(page)
            page.locator('a[aria-label^="Ipanema · Posto 8"]').click()
            page.wait_for_load_state("networkidle")

            caption(page, "Pedro abre o Posto 8 e confere onda, vento, temperatura e chuva acumulada.")
            pause(page)
            page.locator("#recomendacao-ponto").scroll_into_view_if_needed()
            caption(page, "A recomendação explica os motivos e identifica claramente as fontes e a idade dos dados.")
            pause(page, 3000)

            page.get_by_role("link", name="Comparar ponto").click()
            page.wait_for_load_state("networkidle")
            caption(page, "Na comparação, o Posto 10 fica sem recomendação porque não há boletim de qualidade da água.")
            pause(page, 3200)

            page.locator(".comparison-card").nth(3).scroll_into_view_if_needed()
            caption(page, "Outros estados também são explícitos: vento ausente no Posto 11 e boletim vencido no Posto 7.")
            pause(page, 3200)

            page.locator('a.profile-link[href*="perfil=surf"]').click()
            page.wait_for_load_state("networkidle")
            caption(page, "Pedro testa o perfil de surf iniciante e vê a ordem mudar sem alterar as regras de segurança.")
            pause(page, 3000)

            page.locator('a.profile-link[href*="perfil=tranquilo"]').click()
            page.wait_for_load_state("networkidle")
            page.locator(".comparison-card").first.get_by_role("link", name="Entender este ponto").click()
            page.wait_for_load_state("networkidle")
            page.locator("#recomendacao-ponto").scroll_into_view_if_needed()
            caption(page, "Decisão final: Pedro escolhe o Posto 8 para banho tranquilo e sabe por que ele ficou em primeiro.")
            pause(page, 3600)

            video = page.video
            context.close()
            video.save_as(str(RAW_VIDEO))
            browser.close()

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(RAW_VIDEO),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "27",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(FINAL_VIDEO),
        ],
        check=True,
    )
    RAW_VIDEO.unlink(missing_ok=True)
    return FINAL_VIDEO


if __name__ == "__main__":
    print(record())
