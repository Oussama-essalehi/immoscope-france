import { useEffect, useRef } from "react";
import type { Lang } from "../format";
import { useI18n } from "../i18n";
import { LangSwitch } from "./Switches";

interface Props {
  open: boolean;
  onClose: () => void;
  totalSales: number | null;
  lang: Lang;
  onLang: (l: Lang) => void;
}

/**
 * Introduction shown on the first visit (and from the "About" button).
 * Uses the native <dialog> element: focus trapping, Escape key and backdrop
 * come from the browser.
 */
export function WelcomeDialog({ open, onClose, totalSales, lang, onLang }: Props) {
  const { t, f } = useI18n();
  // French typography puts a space before the colon
  const colon = lang === "fr" ? " : " : ": ";
  const ref = useRef<HTMLDialogElement>(null);
  const cta = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
      // showModal() focuses the first control (the language switch): start on the main action instead
      cta.current?.focus({ preventScroll: true });
      dialog.querySelector(".welcome-body")?.scrollTo({ top: 0 });
    }
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className="welcome"
      aria-labelledby="welcome-title"
      onClose={onClose}
      onClick={(e) => {
        // a click on the backdrop (outside the content box) closes the dialog
        if (e.target === ref.current) onClose();
      }}
    >
      <div className="welcome-body">
        <div className="welcome-top">
          <LangSwitch lang={lang} onChange={onLang} />
          <button type="button" className="icon-button" onClick={onClose} aria-label={t("wel.close")}>
            ×
          </button>
        </div>
        <h2 id="welcome-title">{t("wel.title")}</h2>
        <p>{t("wel.intro", { n: totalSales === null ? "…" : f.int(totalSales) })}</p>

        <h3>{t("wel.questionsTitle")}</h3>
        <ul>
          <li>{t("wel.q1")}</li>
          <li>{t("wel.q2")}</li>
          <li>{t("wel.q3")}</li>
        </ul>

        <h3>{t("wel.pagesTitle")}</h3>
        <ul className="welcome-pages">
          <li>
            <strong>{t("nav.overview")}</strong>
            {colon}
            {t("wel.p1")}
          </li>
          <li>
            <strong>{t("nav.map")}</strong>
            {colon}
            {t("wel.p2")}
          </li>
          <li>
            <strong>{t("nav.cities")}</strong>
            {colon}
            {t("wel.p3")}
          </li>
          <li>
            <strong>{t("nav.simulator")}</strong>
            {colon}
            {t("wel.p4")}
          </li>
        </ul>

        <h3>{t("wel.howTitle")}</h3>
        <p>{t("wel.how")}</p>

        <h3>{t("wel.dataTitle")}</h3>
        <p>{t("wel.data")}</p>

        <p className="welcome-author">{t("wel.author")}</p>
      </div>
      <div className="welcome-actions">
        <button ref={cta} type="button" className="primary-button" onClick={onClose}>
          {t("wel.cta")}
        </button>
      </div>
    </dialog>
  );
}
