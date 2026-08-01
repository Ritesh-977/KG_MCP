import { authenticate } from "./auth";

function main(): void {
  if (authenticate("admin")) {
    console.log("ok");
  }
}