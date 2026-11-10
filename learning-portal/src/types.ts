export type DiagramRelation = "traffic" | "ownership" | "control" | "storage" | "configuration";
export type DiagramNode = {
  id: string;
  label: string;
  sublabel?: string;
  description?: string;
  kind: string;
  resource?: string;
  group?: string;
  namespace?: string;
  column?: number;
  contains?: { label: string; technology?: string; resource?: string }[];
};
export type DiagramGroup = {
  id: string;
  label: string;
  kind: "cluster" | "namespace" | "node" | "management" | "aws" | "external";
  parentId?: string;
  description?: string;
};
export type Diagram = {
  type: string;
  title: string;
  caption: string;
  nodes: DiagramNode[];
  edges: { from: string; to: string; label?: string; relation?: DiagramRelation }[];
  groups?: DiagramGroup[];
  views?: { id: string; title: string; description: string; nodeIds: string[]; relations?: DiagramRelation[] }[];
  simulation?: { api: string[]; database: string[]; migration: string[] };
};
export type Phase = {
  id: string;
  slug: string;
  title: string;
  subtitle: string;
  level: string;
  implemented: boolean;
  estimatedMinutes: number;
  summary: string;
  goals: string[];
  concepts: { term: string; description: string; analogy: string }[];
  sections: {
    id: string;
    kind?: string;
    title: string;
    body: string;
    callout?: string;
    steps?: { title: string; description: string; command?: string; linuxCommand?: string; expected?: string }[];
  }[];
  diagram: Diagram;
  questions: { id: string; prompt: string; rubric: string[] }[];
  memoFields: { id: string; label: string }[];
  sources: { label: string; path: string }[];
};
export type Feedback = {
  score: number;
  summary: string;
  strengths: string[];
  improvements: string[];
  questions: { id: string; score: number; maxScore: number; feedback: string; suggestedAnswer: string }[];
  nextSteps: string[];
  gradedAt?: string;
  provider?: string;
};
export type PhaseProgress = {
  notes: Record<string, string>;
  answers: Record<string, string>;
  checklist: Record<string, boolean>;
  completed: boolean;
  updatedAt: string | null;
  feedback: Feedback | null;
  imported?: boolean;
};
export type AiProvider = { id: string; label: string; available: boolean; message: string };
export type Bootstrap = {
  curriculum: { title: string; phases: Phase[] };
  progress: Record<string, PhaseProgress>;
  ai: { providers: AiProvider[] };
};
