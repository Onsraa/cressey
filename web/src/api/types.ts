import type { components } from "./schema";

type Schemas = components["schemas"];

export type Case = Schemas["Case"];
export type CaseEvent = Schemas["Event"];
export type EvalFile = Schemas["EvalFile"];
export type Fix = Schemas["Fix"];
export type FleetSignal = Schemas["FleetSignal"];
export type Guide = Schemas["Guide"];
export type GuideStep = Schemas["GuideStep"];
export type Hold = Schemas["Hold"];
export type Incident = Schemas["Incident"];
export type Leg = Schemas["Leg"];
export type Legs = Schemas["Legs"];
export type Mandate = Schemas["Mandate"];
export type Message = Schemas["Message"];
export type OwnerGuide = Schemas["OwnerGuide"];
export type Replay = Schemas["Replay"];
export type ReplayResult = Schemas["ReplayResult"];
export type Responses = Schemas["Responses"];
export type Run = Schemas["Run"];
export type RunSummary = Schemas["RunSummary"];
export type Secret = Schemas["Secret"];
export type Shadow = Schemas["Shadow"];
export type Source = Schemas["Source"];
export type Status = Schemas["Status"];
export type Step = Schemas["Step"];
export type Thread = Schemas["Thread"];
export type WhyAnswer = Schemas["WhyAnswer"];

export type Indicator = CaseEvent["indicator"];
export type LegName = keyof Legs;
export type StepStatus = NonNullable<Step["status"]>;
