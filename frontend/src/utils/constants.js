export const languageLabelMap = {
    en: 'English',
    es: 'Spanish',
    fr: 'French',
    de: 'German',
    it: 'Italian',
    pt: 'Portuguese',
    ja: 'Japanese',
    ko: 'Korean',
    zhs: 'Simplified Chinese',
    zht: 'Traditional Chinese',
    ru: 'Russian',
  };
  export const labelToCodeMap = Object.fromEntries(
    Object.entries(languageLabelMap).map(([code, label]) => [label, code])
  );
  export const ALLOWED_QUALITIES = ['NM', 'LP', 'MP', 'HP', 'DMG'];