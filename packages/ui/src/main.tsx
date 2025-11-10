import React from "react";
import { render } from "ink";
import { Agent } from "../../server/dist/agent.js";
import { App } from "./App.js";

export function renderUI(
  agent: Agent,
  setMessageHandler: (handler: (message: any) => void) => void
): void {
  render(<App agent={agent} setMessageHandler={setMessageHandler} />);
}
