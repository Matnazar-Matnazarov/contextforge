import { describe, expect, it } from "vitest";
import { registerSchema, validateFile } from "@/lib/schemas";
import { ApiError, errorMessage, formatBytes } from "@/lib/api";

const file = (name: string, size: number) => new File([new Uint8Array(size)], name);

describe("validateFile", () => {
  it("accepts supported types", () => {
    expect(validateFile(file("a.pdf", 10))).toBeNull();
    expect(validateFile(file("NOTES.MD", 10))).toBeNull();
  });
  it("rejects unsupported, empty and oversized files with clear messages", () => {
    expect(validateFile(file("a.exe", 10))).toMatch(/Unsupported/);
    expect(validateFile(file("a.txt", 0))).toMatch(/empty/);
    expect(validateFile(file("a.txt", 11 * 1024 * 1024))).toMatch(/limit/);
  });
});

describe("forms", () => {
  it("register requires a 10 char password", () => {
    expect(registerSchema.safeParse({ email: "a@b.co", password: "short" }).success).toBe(false);
    expect(registerSchema.safeParse({ email: "a@b.co", password: "long-enough-pass" }).success).toBe(true);
  });
});

describe("api helpers", () => {
  it("formats bytes", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2 * 1024 * 1024)).toBe("2.0 MB");
  });
  it("surfaces validation messages and hides unknown errors", () => {
    const e = new ApiError(400, "validation_error", "Invalid input.", { email: ["Already exists."] });
    expect(errorMessage(e)).toBe("Already exists.");
    expect(errorMessage(new Error("TypeError: stack trace"))).toBe("Something went wrong. Please try again.");
  });
});
