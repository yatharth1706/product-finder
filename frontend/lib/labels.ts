import type { FailureReason, Platform } from "./types";

export const PLATFORM_NAMES: Record<Platform, string> = {
  flipkart: "Flipkart",
  croma: "Croma",
  reliance_digital: "Reliance Digital",
  myntra: "Myntra",
};

export const ATTRIBUTE_NAMES: Record<string, string> = {
  brand: "Brand",
  model: "Model",
  ram: "RAM",
  storage: "Storage",
  screen_size: "Screen size",
  colour: "Colour",
};

export const FAILURE_MESSAGES: Record<FailureReason, string> = {
  blocked: "The site blocked our request, so we could not check.",
  timeout: "The site took too long to answer.",
  parse_error: "The site returned a page we could not read.",
  availability_unknown: "Found the same product, but could not tell if it is in stock.",
  unexpected: "Something went wrong while checking this site.",
};
