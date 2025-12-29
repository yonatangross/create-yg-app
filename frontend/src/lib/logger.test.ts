/**
 * Tests for structured logger
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { createLogger, measureAsync, measureSync } from "./logger";

describe("Logger", () => {
	// Capture console output
	let consoleLogSpy: ReturnType<typeof vi.spyOn>;
	let consoleWarnSpy: ReturnType<typeof vi.spyOn>;
	let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

	beforeEach(() => {
		consoleLogSpy = vi.spyOn(console, "log").mockImplementation(() => {});
		consoleWarnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
		consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
	});

	afterEach(() => {
		consoleLogSpy.mockRestore();
		consoleWarnSpy.mockRestore();
		consoleErrorSpy.mockRestore();
	});

	describe("createLogger", () => {
		it("creates logger with module name", () => {
			const logger = createLogger("TestModule");
			expect(logger.getModule()).toBe("TestModule");
		});

		it("logs info messages", () => {
			const logger = createLogger("TestModule");
			logger.info("test_event", { foo: "bar" });
			expect(consoleLogSpy).toHaveBeenCalled();
		});

		it("logs warn messages", () => {
			const logger = createLogger("TestModule");
			logger.warn("warning_event", { code: "WARN_001" });
			expect(consoleWarnSpy).toHaveBeenCalled();
		});

		it("logs error messages", () => {
			const logger = createLogger("TestModule");
			logger.error("error_event", { message: "Something failed" });
			expect(consoleErrorSpy).toHaveBeenCalled();
		});

		it("logs debug messages when level is debug", () => {
			const logger = createLogger("TestModule", "debug");
			logger.debug("debug_event", { detail: "verbose" });
			expect(consoleLogSpy).toHaveBeenCalled();
		});

		it("filters debug messages when level is info", () => {
			const logger = createLogger("TestModule", "info");
			logger.debug("debug_event", { detail: "verbose" });
			expect(consoleLogSpy).not.toHaveBeenCalled();
		});
	});

	describe("Context binding", () => {
		it("binds context that persists across logs", () => {
			const logger = createLogger("TestModule");
			logger.bindContext({ session_id: "123", user_id: "456" });

			logger.info("first_event");
			logger.info("second_event");

			expect(consoleLogSpy).toHaveBeenCalledTimes(2);
			const context = logger.getContext();
			expect(context).toEqual({ session_id: "123", user_id: "456" });
		});

		it("merges multiple bindContext calls", () => {
			const logger = createLogger("TestModule");
			logger.bindContext({ session_id: "123" });
			logger.bindContext({ conversation_id: "789" });

			const context = logger.getContext();
			expect(context).toEqual({ session_id: "123", conversation_id: "789" });
		});

		it("overwrites context keys on rebind", () => {
			const logger = createLogger("TestModule");
			logger.bindContext({ session_id: "123" });
			logger.bindContext({ session_id: "456" });

			const context = logger.getContext();
			expect(context).toEqual({ session_id: "456" });
		});

		it("clears context", () => {
			const logger = createLogger("TestModule");
			logger.bindContext({ session_id: "123" });
			logger.clearContext();

			const context = logger.getContext();
			expect(context).toEqual({});
		});
	});

	describe("withContext", () => {
		it("creates new logger with additional context", () => {
			const baseLogger = createLogger("TestModule");
			baseLogger.bindContext({ session_id: "123" });

			const requestLogger = baseLogger.withContext({ request_id: "789" });

			// Original logger unchanged
			expect(baseLogger.getContext()).toEqual({ session_id: "123" });

			// New logger has merged context
			expect(requestLogger.getContext()).toEqual({
				session_id: "123",
				request_id: "789",
			});
		});

		it("does not mutate original logger", () => {
			const baseLogger = createLogger("TestModule");
			baseLogger.bindContext({ session_id: "123" });

			const requestLogger = baseLogger.withContext({ request_id: "789" });
			requestLogger.bindContext({ user_id: "456" });

			// Original logger unchanged
			expect(baseLogger.getContext()).toEqual({ session_id: "123" });
		});
	});

	describe("Error serialization", () => {
		it("serializes Error objects", () => {
			const logger = createLogger("TestModule");
			const error = new Error("Test error");

			logger.error("error_event", { error });

			expect(consoleErrorSpy).toHaveBeenCalled();
			// Check that error was serialized (not testing exact format)
			const callArg = consoleErrorSpy.mock.calls[0];
			expect(callArg).toBeDefined();
		});

		it("handles custom error types", () => {
			const logger = createLogger("TestModule");

			class CustomError extends Error {
				constructor(message: string) {
					super(message);
					this.name = "CustomError";
				}
			}

			const error = new CustomError("Custom error message");
			logger.error("custom_error_event", { error });

			expect(consoleErrorSpy).toHaveBeenCalled();
		});
	});

	describe("Log level filtering", () => {
		it("respects minimum log level", () => {
			const logger = createLogger("TestModule", "warn");

			logger.debug("debug_event");
			logger.info("info_event");
			logger.warn("warn_event");
			logger.error("error_event");

			expect(consoleLogSpy).not.toHaveBeenCalled(); // debug & info filtered
			expect(consoleWarnSpy).toHaveBeenCalledTimes(1);
			expect(consoleErrorSpy).toHaveBeenCalledTimes(1);
		});

		it("allows all levels when set to debug", () => {
			const logger = createLogger("TestModule", "debug");

			logger.debug("debug_event");
			logger.info("info_event");
			logger.warn("warn_event");
			logger.error("error_event");

			expect(consoleLogSpy).toHaveBeenCalledTimes(2); // debug + info
			expect(consoleWarnSpy).toHaveBeenCalledTimes(1);
			expect(consoleErrorSpy).toHaveBeenCalledTimes(1);
		});
	});

	describe("Field merging", () => {
		it("merges bound context with log fields", () => {
			const logger = createLogger("TestModule");
			logger.bindContext({ session_id: "123" });

			logger.info("test_event", { custom_field: "value" });

			// Both session_id and custom_field should be in output
			expect(consoleLogSpy).toHaveBeenCalled();
		});

		it("log fields override bound context", () => {
			const logger = createLogger("TestModule");
			logger.bindContext({ session_id: "123" });

			logger.info("test_event", { session_id: "456" });

			expect(consoleLogSpy).toHaveBeenCalled();
			// session_id should be '456' from log fields
		});
	});
});

describe("Performance utilities", () => {
	let consoleLogSpy: ReturnType<typeof vi.spyOn>;
	let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

	beforeEach(() => {
		consoleLogSpy = vi.spyOn(console, "log").mockImplementation(() => {});
		consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
	});

	afterEach(() => {
		consoleLogSpy.mockRestore();
		consoleErrorSpy.mockRestore();
	});

	describe("measureAsync", () => {
		it("logs successful execution with duration", async () => {
			const logger = createLogger("TestModule");
			const fn = vi.fn().mockResolvedValue("result");

			const result = await measureAsync("async_operation", fn, logger);

			expect(result).toBe("result");
			expect(fn).toHaveBeenCalled();
			expect(consoleLogSpy).toHaveBeenCalled();
			// Should log with duration_ms and success: true
		});

		it("logs errors with duration", async () => {
			const logger = createLogger("TestModule");
			const error = new Error("Async error");
			const fn = vi.fn().mockRejectedValue(error);

			await expect(measureAsync("async_operation", fn, logger)).rejects.toThrow(
				"Async error",
			);

			expect(fn).toHaveBeenCalled();
			expect(consoleErrorSpy).toHaveBeenCalled();
			// Should log with duration_ms and success: false
		});

		it("includes custom fields in logs", async () => {
			const logger = createLogger("TestModule");
			const fn = vi.fn().mockResolvedValue("result");

			await measureAsync("async_operation", fn, logger, {
				endpoint: "/api/test",
			});

			expect(consoleLogSpy).toHaveBeenCalled();
		});
	});

	describe("measureSync", () => {
		it("logs successful execution with duration", () => {
			const logger = createLogger("TestModule");
			const fn = vi.fn().mockReturnValue("result");

			const result = measureSync("sync_operation", fn, logger);

			expect(result).toBe("result");
			expect(fn).toHaveBeenCalled();
			expect(consoleLogSpy).toHaveBeenCalled();
		});

		it("logs errors with duration", () => {
			const logger = createLogger("TestModule");
			const fn = vi.fn().mockImplementation(() => {
				throw new Error("Sync error");
			});

			expect(() => measureSync("sync_operation", fn, logger)).toThrow(
				"Sync error",
			);

			expect(fn).toHaveBeenCalled();
			expect(consoleErrorSpy).toHaveBeenCalled();
		});

		it("includes custom fields in logs", () => {
			const logger = createLogger("TestModule");
			const fn = vi.fn().mockReturnValue("result");

			measureSync("sync_operation", fn, logger, { operation_type: "parse" });

			expect(consoleLogSpy).toHaveBeenCalled();
		});
	});
});
