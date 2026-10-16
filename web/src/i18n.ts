/** Language context: translated texts (`t`) and matching number formatters (`f`). */
import { createContext, useContext } from "react";
import { makeFormatters, type Formatters, type Lang } from "./format";
import { en, fr, type MessageKey } from "./locales";

const DICTIONARIES: Record<Lang, Record<MessageKey, string>> = { fr, en };

export interface I18n {
  lang: Lang;
  t: (key: MessageKey, vars?: Record<string, string | number>) => string;
  f: Formatters;
}

export function makeI18n(lang: Lang): I18n {
  const dictionary = DICTIONARIES[lang];
  return {
    lang,
    t: (key, vars) =>
      Object.entries(vars ?? {}).reduce((text, [name, value]) => text.split(`{${name}}`).join(String(value)), dictionary[key]),
    f: makeFormatters(lang),
  };
}

export const I18nContext = createContext<I18n>(makeI18n("fr"));
export const useI18n = (): I18n => useContext(I18nContext);

/** Language from the browser: French for French-speaking visitors, English otherwise. */
export function browserLang(): Lang {
  return typeof navigator !== "undefined" && navigator.language?.toLowerCase().startsWith("fr") ? "fr" : "en";
}
