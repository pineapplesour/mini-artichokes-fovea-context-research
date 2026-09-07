export type DomainKey = "islam" | "tcm" | "psychology";

export type DomainProduct = {
  key: DomainKey;
  name: string;
  shortName: string;
  defaultLanguage: string;
  languages: string[];
  route: string;
  referenceLayout: "islam-centered-thread" | "hanji-consult" | "therapeutic-aurora";
  postQueryWorkspace: {
    mode: "isnad-chat-history";
    railLabel: string;
    evidenceLabel: string;
    corpusLabel: string;
  };
  eyebrow: string;
  headline: string;
  subline: string;
  examples: Array<{ label: string; query: string }>;
  safetyNotice: string;
};

export type DomainLocaleCopy = {
  direction: "ltr" | "rtl";
  askLabel: string;
  sendLabel: string;
  cancelLabel: string;
  answerLabel: string;
  sourcesLabel: string;
  safetyLabel: string;
  emptyAnswer: string;
  emptySources: string;
  examplesLabel: string;
  queryPlaceholder: string;
};

export type DomainPalette = {
  page: string;
  surface: string;
  surfaceAlt: string;
  text: string;
  muted: string;
  line: string;
  accent: string;
  accentAlt: string;
  motif: string;
  radius: number;
  colorScheme: "light" | "dark";
};

export const DOMAIN_PRODUCTS: Record<DomainKey, DomainProduct> = {
  islam: {
    key: "islam",
    name: "Hikmah",
    shortName: "HIKMAH",
    defaultLanguage: "en",
    languages: ["en", "ko", "ar", "pa", "ur", "bn", "id", "ms", "fa", "tr", "sw"],
    route: "/domain/islam",
    referenceLayout: "islam-centered-thread",
    postQueryWorkspace: {
      mode: "isnad-chat-history",
      railLabel: "Archive",
      evidenceLabel: "Evidence",
      corpusLabel: "Qur'an · Hadith · Tafsir",
    },
    eyebrow: "ASK · LEARN · REFLECT",
    headline: "Hikmah",
    subline: "ٱلْعِلْمُ نُور",
    examples: [
      { label: "Qibla", query: "qibla prayer evidence" },
      { label: "Prayer time", query: "prayer time ruling source" },
      { label: "Fasting", query: "fasting mercy hardship" },
    ],
    safetyNotice:
      "Grounded religious-study aid only. It is not a binding fatwa or authoritative Qur'an translation.",
  },
  tcm: {
    key: "tcm",
    name: "醫源 · 의원",
    shortName: "UIWON",
    defaultLanguage: "ko",
    languages: ["ko", "en"],
    route: "/domain/tcm",
    referenceLayout: "hanji-consult",
    postQueryWorkspace: {
      mode: "isnad-chat-history",
      railLabel: "문진 기록",
      evidenceLabel: "문헌 근거",
      corpusLabel: "고전 · 본초 · 침구",
    },
    eyebrow: "韓醫學 · KOREAN MEDICINE AI · MMXXVI",
    headline: "오래된 지혜를, 새로운 방식으로",
    subline: "천 년의 한의학을 문헌 근거로 묻다.",
    examples: [
      { label: "Pattern", query: "소화불량과 한열 변증" },
      { label: "Formula", query: "감초의 고문헌 근거" },
      { label: "Acupuncture", query: "insomnia acupuncture classical evidence" },
    ],
    safetyNotice:
      "문헌 기반 정보 도구이며 진단이나 치료 지시가 아닙니다. 증상은 의료 전문가와 상담하세요.",
  },
  psychology: {
    key: "psychology",
    name: "마음결",
    shortName: "MAEUMGYEOL",
    defaultLanguage: "ko",
    languages: ["ko", "en"],
    route: "/domain/psychology",
    referenceLayout: "therapeutic-aurora",
    postQueryWorkspace: {
      mode: "isnad-chat-history",
      railLabel: "Sessions",
      evidenceLabel: "Evidence",
      corpusLabel: "Guidelines · Papers",
    },
    eyebrow: "A · Quiet Editorial",
    headline: "서두르지 않는 마음 탐색",
    subline: "마음결 — 4가지 디자인 방향 · fig. 01",
    examples: [
      { label: "Crisis", query: "self harm crisis safety planning" },
      { label: "Safety plan", query: "panic worry grounding skills" },
      { label: "Sleep", query: "수면 문제와 우울감" },
    ],
    safetyNotice:
      "진단이 아닙니다. 자해·타해 위험이나 즉시 위험이 있으면 현지 긴급 도움을 먼저 요청하세요.",
  },
};

const DEFAULT_LOCALE_COPY: DomainLocaleCopy = {
  direction: "ltr",
  askLabel: "Ask",
  sendLabel: "Ask",
  cancelLabel: "Stop",
  answerLabel: "Grounded answer",
  sourcesLabel: "Sources",
  safetyLabel: "Safety boundary",
  emptyAnswer: "Source-grounded response will appear here.",
  emptySources: "Retrieved evidence cards will appear here.",
  examplesLabel: "Try",
  queryPlaceholder: "Ask a source-grounded question.",
};

const DOMAIN_LOCALE_COPY: Partial<Record<DomainKey, Partial<Record<string, Partial<DomainLocaleCopy>>>>> = {
  islam: {
    en: {
      examplesLabel: "Suggested questions",
      queryPlaceholder: "Ask about prayer, fasting, mercy, or a source passage.",
    },
    ko: {
      askLabel: "묻기",
      sendLabel: "질문",
      cancelLabel: "중지",
      answerLabel: "근거 기반 답변",
      sourcesLabel: "근거",
      safetyLabel: "안전 경계",
      emptyAnswer: "검색 근거에 기반한 답변이 여기에 표시됩니다.",
      emptySources: "검색된 근거 카드가 여기에 표시됩니다.",
      examplesLabel: "추천 질문",
      queryPlaceholder: "예배, 금식, 자비, 꾸란/하디스 근거를 물어보세요.",
    },
    ar: {
      direction: "rtl",
      askLabel: "اسأل",
      sendLabel: "اسأل",
      cancelLabel: "إيقاف",
      answerLabel: "إجابة موثقة",
      sourcesLabel: "المصادر",
      safetyLabel: "حدود السلامة",
      emptyAnswer: "ستظهر هنا إجابة موثقة بالمصادر.",
      emptySources: "ستظهر هنا بطاقات المصادر المسترجعة.",
      examplesLabel: "أسئلة مقترحة",
      queryPlaceholder: "اسأل عن الصلاة أو الصيام أو الرحمة أو الدليل.",
    },
    pa: {
      askLabel: "ਪੁੱਛੋ",
      sendLabel: "ਪੁੱਛੋ",
      cancelLabel: "ਰੋਕੋ",
      answerLabel: "ਸਰੋਤ-ਅਧਾਰਿਤ ਜਵਾਬ",
      sourcesLabel: "ਸਰੋਤ",
      safetyLabel: "ਸੁਰੱਖਿਆ ਸੀਮਾ",
      emptyAnswer: "ਸਰੋਤਾਂ ਨਾਲ ਜੁੜਿਆ ਜਵਾਬ ਇੱਥੇ ਦਿਖੇਗਾ।",
      emptySources: "ਮਿਲੇ ਹੋਏ ਸਰੋਤ ਕਾਰਡ ਇੱਥੇ ਦਿਖਣਗੇ।",
      examplesLabel: "ਸੁਝਾਅ",
      queryPlaceholder: "ਨਮਾਜ਼, ਰੋਜ਼ਾ, ਰਹਿਮਤ ਜਾਂ ਕਿਸੇ ਸਰੋਤ ਬਾਰੇ ਪੁੱਛੋ।",
    },
    ur: {
      direction: "rtl",
      askLabel: "پوچھیں",
      sendLabel: "پوچھیں",
      cancelLabel: "روکیں",
      answerLabel: "مستند جواب",
      sourcesLabel: "ماخذ",
      safetyLabel: "حفاظتی حد",
      emptyAnswer: "ماخذ پر مبنی جواب یہاں ظاہر ہوگا۔",
      emptySources: "حاصل شدہ ماخذی کارڈ یہاں ظاہر ہوں گے۔",
      examplesLabel: "تجویز کردہ سوالات",
      queryPlaceholder: "نماز، روزہ، رحمت یا کسی دلیل کے بارے میں پوچھیں۔",
    },
    bn: {
      askLabel: "জিজ্ঞাসা করুন",
      sendLabel: "জিজ্ঞাসা",
      cancelLabel: "থামান",
      answerLabel: "প্রমাণভিত্তিক উত্তর",
      sourcesLabel: "সূত্র",
      safetyLabel: "নিরাপত্তা সীমা",
      emptyAnswer: "উৎসভিত্তিক উত্তর এখানে দেখা যাবে।",
      emptySources: "উদ্ধার করা সূত্র কার্ড এখানে দেখা যাবে।",
      examplesLabel: "প্রস্তাবিত প্রশ্ন",
      queryPlaceholder: "নামাজ, রোজা, রহমত বা কোনো উৎসাংশ সম্পর্কে জিজ্ঞাসা করুন।",
    },
    id: {
      askLabel: "Tanya",
      sendLabel: "Tanya",
      cancelLabel: "Henti",
      answerLabel: "Jawaban berbasis sumber",
      sourcesLabel: "Sumber",
      safetyLabel: "Batas keamanan",
      emptyAnswer: "Jawaban berbasis sumber akan muncul di sini.",
      emptySources: "Kartu sumber yang ditemukan akan muncul di sini.",
      examplesLabel: "Saran",
      queryPlaceholder: "Tanyakan tentang salat, puasa, rahmat, atau bukti sumber.",
    },
    ms: {
      askLabel: "Tanya",
      sendLabel: "Tanya",
      cancelLabel: "Henti",
      answerLabel: "Jawapan berasaskan sumber",
      sourcesLabel: "Sumber",
      safetyLabel: "Batas keselamatan",
      emptyAnswer: "Jawapan berasaskan sumber akan dipaparkan di sini.",
      emptySources: "Kad sumber yang ditemui akan dipaparkan di sini.",
      examplesLabel: "Cadangan",
      queryPlaceholder: "Tanya tentang solat, puasa, rahmat, atau bukti sumber.",
    },
    fa: {
      direction: "rtl",
      askLabel: "بپرسید",
      sendLabel: "بپرسید",
      cancelLabel: "توقف",
      answerLabel: "پاسخ مستند",
      sourcesLabel: "منابع",
      safetyLabel: "مرز ایمنی",
      emptyAnswer: "پاسخ مبتنی بر منبع اینجا نمایش داده می‌شود.",
      emptySources: "کارت‌های منابع بازیابی‌شده اینجا نمایش داده می‌شوند.",
      examplesLabel: "پرسش‌های پیشنهادی",
      queryPlaceholder: "درباره نماز، روزه، رحمت یا یک شاهد منبعی بپرسید.",
    },
    tr: {
      askLabel: "Sor",
      sendLabel: "Sor",
      cancelLabel: "Durdur",
      answerLabel: "Kaynak temelli yanıt",
      sourcesLabel: "Kaynaklar",
      safetyLabel: "Güvenlik sınırı",
      emptyAnswer: "Kaynak temelli yanıt burada görünecek.",
      emptySources: "Getirilen kaynak kartları burada görünecek.",
      examplesLabel: "Öneriler",
      queryPlaceholder: "Namaz, oruç, merhamet veya kaynak kanıtı hakkında sorun.",
    },
    sw: {
      askLabel: "Uliza",
      sendLabel: "Uliza",
      cancelLabel: "Simamisha",
      answerLabel: "Jibu lenye msingi wa vyanzo",
      sourcesLabel: "Vyanzo",
      safetyLabel: "Mpaka wa usalama",
      emptyAnswer: "Jibu lenye msingi wa vyanzo litaonekana hapa.",
      emptySources: "Kadi za vyanzo vilivyopatikana zitaonekana hapa.",
      examplesLabel: "Mapendekezo",
      queryPlaceholder: "Uliza kuhusu sala, kufunga, rehema, au ushahidi wa chanzo.",
    },
  },
  tcm: {
    ko: {
      askLabel: "묻기",
      sendLabel: "질문",
      cancelLabel: "중지",
      answerLabel: "문헌 근거 답변",
      sourcesLabel: "문헌",
      safetyLabel: "진료 안전 경계",
      emptyAnswer: "문헌 근거 답변이 여기에 표시됩니다.",
      emptySources: "검색된 고문헌/논문 근거가 여기에 표시됩니다.",
      examplesLabel: "예시 질문",
      queryPlaceholder: "요즘 손발이 차고 자주 피곤합니다...",
    },
    en: {
      answerLabel: "Classical evidence answer",
      cancelLabel: "Stop",
      sourcesLabel: "Texts",
      safetyLabel: "Clinical safety boundary",
      examplesLabel: "Prompts",
      queryPlaceholder: "Ask about a symptom, herb, formula, or pattern.",
    },
  },
  psychology: {
    ko: {
      askLabel: "묻기",
      sendLabel: "질문",
      cancelLabel: "중지",
      answerLabel: "근거 기반 정리",
      sourcesLabel: "근거",
      safetyLabel: "안전 경계",
      emptyAnswer: "근거 기반 정리가 여기에 표시됩니다.",
      emptySources: "검색된 심리·정신건강 근거가 여기에 표시됩니다.",
      examplesLabel: "부드러운 시작",
      queryPlaceholder: "불안, 수면, 위기 안전계획에 대해 물어보세요.",
    },
    en: {
      askLabel: "Ask",
      sendLabel: "Ask",
      cancelLabel: "Stop",
      answerLabel: "Evidence-based note",
      sourcesLabel: "Evidence",
      safetyLabel: "Safety boundary",
      examplesLabel: "Gentle starts",
      queryPlaceholder: "Ask about anxiety, sleep, grounding, or safety planning.",
    },
  },
};

const PALETTES: Record<DomainKey, DomainPalette> = {
  islam: {
    page: "#071822",
    surface: "#0d2b34",
    surfaceAlt: "#133e48",
    text: "#f6edd9",
    muted: "#c9bea5",
    line: "rgba(212,175,55,0.28)",
    accent: "#c9a86b",
    accentAlt: "#4a8a7b",
    motif: "mihrab-arabesque",
    radius: 6,
    colorScheme: "dark",
  },
  tcm: {
    page: "#faf6ec",
    surface: "#fffdf6",
    surfaceAlt: "#ebe2cd",
    text: "#1c1a17",
    muted: "#6b6052",
    line: "rgba(28,26,23,0.18)",
    accent: "#b6543a",
    accentAlt: "#6b8a78",
    motif: "paper-grain-celadon",
    radius: 4,
    colorScheme: "light",
  },
  psychology: {
    page: "#f0eee9",
    surface: "#fffdf8",
    surfaceAlt: "#e8ece7",
    text: "#26231f",
    muted: "#696a73",
    line: "rgba(38,35,31,0.14)",
    accent: "#a14a2b",
    accentAlt: "#637b8f",
    motif: "therapeutic-rings",
    radius: 8,
    colorScheme: "light",
  },
};

export function getDomainProduct(key: string): DomainProduct {
  const normalized = key === "simli" ? "psychology" : key;
  return DOMAIN_PRODUCTS[(normalized as DomainKey) || "islam"] ?? DOMAIN_PRODUCTS.islam;
}

export function buildDomainPalette(key: string): DomainPalette {
  const normalized = getDomainProduct(key).key;
  return PALETTES[normalized];
}

export function normalizeDomainLanguage(key: string, language: string): string {
  const product = getDomainProduct(key);
  const normalized = String(language || "").trim().toLowerCase();
  return product.languages.includes(normalized) ? normalized : product.defaultLanguage;
}

export function getDomainLocaleCopy(key: string, language: string): DomainLocaleCopy {
  const product = getDomainProduct(key);
  const normalized = normalizeDomainLanguage(product.key, language);
  return {
    ...DEFAULT_LOCALE_COPY,
    ...(DOMAIN_LOCALE_COPY[product.key]?.[normalized] || DOMAIN_LOCALE_COPY[product.key]?.[product.defaultLanguage] || {}),
  };
}

export function buildDomainJobEndpoint(key: string): string {
  return `/api/domain/${getDomainProduct(key).key}/jobs`;
}

export function buildDomainAnswerEndpoint(key: string): string {
  return `/api/domain/${getDomainProduct(key).key}/answer`;
}

export function buildDomainJobResultEndpoint(jobId: string): string {
  return `/api/domain/jobs/${encodeURIComponent(jobId)}/result`;
}

export function buildDomainJobStatusEndpoint(jobId: string): string {
  return `/api/domain/jobs/${encodeURIComponent(jobId)}`;
}
