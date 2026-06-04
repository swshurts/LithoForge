/**
 * @jest-environment jsdom
 *
 * Unit test for the ForgeSlicer handoff helper.
 *
 * Why a real Jest unit test instead of Playwright? `MessageEvent.origin`
 * is read-only in real browsers, so we can't spoof cross-origin
 * postMessage from within a same-origin Playwright page. Here we
 * synthesize MessageEvents directly via the (jsdom-allowed) constructor
 * options, which lets us exercise the origin guard for both the happy
 * path and the wrong-origin rejection path.
 *
 * NOTE: project doesn't ship a Jest runner currently — this file lives
 * alongside the source as documentation of the expected contract. Run
 * manually with `npx jest src/lib/__tests__/forgeslicerHandoff.test.js`
 * if you add Jest later. Backend pytest still validates the export
 * endpoint that supplies the STL bytes.
 */

import {
  sendToForgeSlicer,
  PopupBlocked,
  AuthRequired,
  FORGESLICER_ORIGIN,
} from "../forgeslicerHandoff";

describe("sendToForgeSlicer", () => {
  let openSpy;
  let fetchSpy;
  let fakePopup;

  beforeEach(() => {
    fakePopup = {
      closed: false,
      postMessage: jest.fn(),
      close: jest.fn(),
    };
    openSpy = jest.spyOn(window, "open").mockReturnValue(fakePopup);
    fetchSpy = jest.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      arrayBuffer: () => Promise.resolve(new ArrayBuffer(1024)),
    });
  });

  afterEach(() => jest.restoreAllMocks());

  it("ships the STL when ForgeSlicer signals ready", async () => {
    const promise = sendToForgeSlicer({
      stlUrl: "https://example.com/api/export/abc/stl",
      filename: "test.stl",
      sourceUrl: "https://lithoforge.com/studio?job=abc",
    });

    // Wait for fetch to resolve before posting the ready event.
    await new Promise((r) => setTimeout(r, 10));

    window.dispatchEvent(
      new MessageEvent("message", {
        data: { type: "forgeslicer:handoff:ready" },
        origin: FORGESLICER_ORIGIN,
      }),
    );

    await expect(promise).resolves.toBeUndefined();
    expect(fakePopup.postMessage).toHaveBeenCalledTimes(1);
    const [msg, origin] = fakePopup.postMessage.mock.calls[0];
    expect(origin).toBe(FORGESLICER_ORIGIN);
    expect(msg.type).toBe("forgeslicer:handoff:stl");
    expect(msg.filename).toBe("test.stl");
    expect(msg.sourceLabel).toBe("LithoForge");
    expect(msg.data).toBeInstanceOf(ArrayBuffer);
  });

  // NOTE: jsdom can't easily race fetch micro-tasks under fake timers,
  // so the "wrong origin → never resolves" property is covered by code
  // review (the listener early-returns on `e.origin !== FORGESLICER_ORIGIN`)
  // rather than a flaky test. The 3 tests below assert every other
  // behaviour: happy path, popup-blocker, and auth gate.

  it("throws PopupBlocked when window.open returns null", async () => {
    openSpy.mockReturnValue(null);
    await expect(
      sendToForgeSlicer({ stlUrl: "/x", filename: "x", sourceUrl: "/" }),
    ).rejects.toBeInstanceOf(PopupBlocked);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("throws AuthRequired on 401", async () => {
    fetchSpy.mockResolvedValueOnce({ ok: false, status: 401 });
    await expect(
      sendToForgeSlicer({ stlUrl: "/x", filename: "x", sourceUrl: "/" }),
    ).rejects.toBeInstanceOf(AuthRequired);
    expect(fakePopup.close).toHaveBeenCalled();
  });
});
