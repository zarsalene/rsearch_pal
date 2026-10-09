import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({ api: { play: vi.fn(), newRound: vi.fn(), finishRound: vi.fn(), buyItem: vi.fn(), placeItem: vi.fn() } }));
import { api } from "./api.js";
import DuckIsland from "./Play.jsx";

const STATE = {
  coins: { work: 13, play: 4, spent: 5, balance: 12, play_today: 4, play_cap: 15 },
  grid: { w: 12, h: 8 },
  spots: [{ code: "quotes", x: 2, y: 2 }, { code: "terms", x: 9, y: 2 }, { code: "shop", x: 5, y: 6 }],
  games: [{ code: "quotes", name: "Quote Hunt", text: "A quote." }, { code: "terms", name: "Word Match", text: "A word." }],
  material: { quotes: 4, terms: 3, papers: 2 },
  shop: [
    { code: "flower", name: "Flower", cost: 5, owned: true, x: 3, y: 3 },
    { code: "tree", name: "Tree", cost: 10, owned: false, x: -1, y: -1 },
    { code: "fountain", name: "Fountain", cost: 60, owned: false, x: -1, y: -1 },
  ],
};
const ROUND = { id: "r1", game: "quotes", name: "Quote Hunt", finished: false, questions: [{ prompt: "A quote about agents.", options: ["Paper A", "Paper B"] }, { prompt: "A quote about pasta.", options: ["Paper A", "Paper B"] }, { prompt: "A third quote.", options: ["Paper A", "Paper B"] }] };

beforeEach(() => {
  vi.clearAllMocks();
  api.play.mockResolvedValue(STATE);
});

describe("Duck Island", () => {
  it("shows the coins, where they come from, and the daily limit", async () => {
    render(<DuckIsland notify={() => {}} />);
    expect(await screen.findByText("12 coins")).toBeInTheDocument();
    expect(screen.getByText(/play coins today 4 of 15/)).toBeInTheDocument();
    expect(screen.getByText(/Play gives no points and no levels/)).toBeInTheDocument();
    expect(screen.getByText(/4 checked quotes and 3 saved words/)).toBeInTheDocument();
  });

  it("plays a round, then shows the result with the quote and the page of each source", async () => {
    api.newRound.mockResolvedValue(ROUND);
    api.finishRound.mockResolvedValue({ score: 2, total: 3, coins: 2, capped: false, message: "Good play.", answers: [
      { correct: 0, chosen: 0, source: { title: "Paper A", page: 2, quote: "Our system uses agents." } },
      { correct: 1, chosen: 1, source: { title: "Paper B", page: 1, quote: "Boil the pasta." } },
      { correct: 0, chosen: 1, source: { title: "Paper A", page: 3, quote: "A third source." } }] });
    render(<DuckIsland notify={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: /Go to Quote Hunt/ }));
    expect(await screen.findByText("A quote about agents.")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Paper A" })[0]);
    await userEvent.click(screen.getAllByRole("button", { name: "Paper B" })[0]);
    await userEvent.click(screen.getAllByRole("button", { name: "Paper B" })[0]);
    expect(api.finishRound).toHaveBeenCalledWith("r1", [0, 1, 1]);
    expect(await screen.findByText("2 of 3 right")).toBeInTheDocument();
    expect(screen.getByText(/You win/)).toHaveTextContent("2 coins");
    expect(screen.getByText(/page 3/)).toBeInTheDocument();
    expect(screen.getByText(/Not this time/)).toBeInTheDocument();
  });

  it("says when the coins for today are full, and that play is still allowed", async () => {
    api.newRound.mockResolvedValue(ROUND);
    api.finishRound.mockResolvedValue({ score: 3, total: 3, coins: 0, capped: true, message: "Perfect round.", answers: ROUND.questions.map(() => ({ correct: 0, chosen: 0, source: { title: "Paper A", page: 1, quote: "q" } })) });
    render(<DuckIsland notify={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: /Go to Quote Hunt/ }));
    for (let i = 0; i < 3; i++) await userEvent.click(screen.getAllByRole("button", { name: "Paper A" })[0]);
    expect(await screen.findByText(/coins for today are full. You can still play for fun/)).toBeInTheDocument();
  });

  it("stops a round without a penalty", async () => {
    api.newRound.mockResolvedValue(ROUND);
    render(<DuckIsland notify={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: /Go to Quote Hunt/ }));
    await userEvent.click(screen.getByRole("button", { name: /Stop. No coins, no penalty/ }));
    expect(screen.queryByText("A quote about agents.")).not.toBeInTheDocument();
    expect(api.finishRound).not.toHaveBeenCalled();
  });

  it("shows the server message when a round cannot start", async () => {
    api.newRound.mockRejectedValue(new Error("Quote Hunt needs 2 papers that are ready."));
    const notify = vi.fn();
    render(<DuckIsland notify={notify} />);
    await userEvent.click(await screen.findByRole("button", { name: /Go to Quote Hunt/ }));
    await waitFor(() => expect(notify).toHaveBeenCalledWith("Quote Hunt needs 2 papers that are ready."));
  });

  it("buys an item that the coins allow, and disables an item that they do not", async () => {
    api.buyItem.mockResolvedValue({ ...STATE, coins: { ...STATE.coins, balance: -1 } });
    render(<DuckIsland notify={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: /Go to the Shop/ }));
    expect(screen.getByRole("button", { name: "Buy Fountain for 60 coins" })).toBeDisabled();
    expect(screen.getByText("You have it.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Buy Tree for 10 coins" }));
    expect(api.buyItem).toHaveBeenCalledWith("tree");
  });

  it("places an item where the Duck stands", async () => {
    api.placeItem.mockResolvedValue(STATE);
    render(<DuckIsland notify={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: "Decorate" }));
    await userEvent.click(screen.getByRole("button", { name: "Place at the Duck" }));
    expect(api.placeItem).toHaveBeenCalledWith("flower", 6, 4);
  });

  it("walks with the arrow keys and opens the game place when the Duck steps on it", async () => {
    api.newRound.mockResolvedValue(ROUND);
    render(<DuckIsland notify={() => {}} />);
    const wrap = await screen.findByRole("application");
    wrap.focus();
    // from tile 6,4 to the Word Match place 9,2: right x3, up x2
    for (const k of ["ArrowRight", "ArrowRight", "ArrowRight", "ArrowUp", "ArrowUp"]) await userEvent.keyboard(`{${k}}`);
    await waitFor(() => expect(api.newRound).toHaveBeenCalledWith("terms"));
  });
});
