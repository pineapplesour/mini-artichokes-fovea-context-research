export type MockPrecedent = {
  id: string;
  caseNumber: string;
  title: string;
  court: string;
  decisionDate: string;
  tags: string[];
  summary: string;
  context: string;
  usedQuote: string;
};

export const workspaceModes = [
  { id: "question", label: "질문" },
  { id: "document", label: "문서" },
];

export const precedentHistory = [
  { id: "session-01", title: "음주운전 징계 무효 전략 초안", meta: "19개 판례 · claim 34개" },
  { id: "session-02", title: "채무불이행과 사기 구별 질문", meta: "31개 판례 · claim 22개" },
  { id: "session-03", title: "공익신고 후 명예훼손 리스크", meta: "27개 판례 · claim 18개" },
];

export const livePrecedents: MockPrecedent[] = [
  {
    id: "p-2020-1",
    caseNumber: "2020구합12259",
    title: "감봉 3월 징계처분 무효 확인 사건",
    court: "서울행정법원",
    decisionDate: "2021-06-17",
    tags: ["징계시효", "이중징계", "감봉"],
    summary:
      "비위 인지와 징계 요구 사이의 시간 경과, 선행 조치의 성격, 후행 징계의 누적 방식이 핵심 판단축으로 정리된 사건입니다.",
    context:
      "같은 비위군을 뒤늦게 다시 징계 사유로 편입시키는 방식이 적법한지, 그리고 징계권자가 이미 사실을 파악하고도 방치했는지가 주요 쟁점으로 다뤄졌습니다.",
    usedQuote:
      "징계권자가 이미 그 비위사실을 인지하고 상당한 기간 아무런 조치를 취하지 아니하였다면, 이후 이를 다시 징계사유에 포함시키는 것은 신뢰보호 원칙 및 재량권 일탈·남용의 문제를 발생시킬 수 있다.",
  },
  {
    id: "p-2016-1",
    caseNumber: "2016구합7279",
    title: "군 징계처분 취소 사건",
    court: "서울행정법원",
    decisionDate: "2017-07-14",
    tags: ["재량권 남용", "군 징계", "감봉"],
    summary:
      "징계 사유의 중대성과 징계 수위 사이의 비례성 판단, 그리고 비슷한 선례와의 불균형 여부가 문제된 사건입니다.",
    context:
      "처분사유 자체는 인정되더라도, 동일·유사 사안과 비교했을 때 과도한 징계인지가 독립 쟁점으로 검토되었습니다.",
    usedQuote:
      "징계권자에게 재량이 인정된다고 하더라도, 그 재량 행사가 사회통념상 현저히 타당성을 잃은 경우에는 재량권의 일탈·남용으로서 위법하다.",
  },
  {
    id: "p-2017-1",
    caseNumber: "2017구합12068",
    title: "징계부가금 및 징계처분 취소 사건",
    court: "의정부지방법원",
    decisionDate: "2018-05-31",
    tags: ["신뢰보호", "절차", "징계부가금"],
    summary:
      "사전 통지와 절차적 대응 기회가 부족했던 경우, 본안 논리와 별개로 절차 위법이 강하게 작동할 수 있음을 보여주는 사건입니다.",
    context:
      "실체 판단만으로 결론이 닫히지 않고, 사전 고지 내용과 방어권 보장 수준이 처분 위법성의 독립 축으로 평가되었습니다.",
    usedQuote:
      "당사자가 방어권을 실질적으로 행사할 수 있을 정도로 구체적인 사전통지가 이루어지지 아니한 이상, 그 처분은 절차상 하자를 안고 있다고 보아야 한다.",
  },
];

export const mockRunProfile = {
  workerCount: 4,
  chunkBatchSize: 3,
  totalChunks: 64,
  initialCompleted: 17,
  initialElapsedSeconds: 93,
  secondsPerTick: 5,
  tickMs: 1800,
  chunkAdvancePerTick: 2,
};
