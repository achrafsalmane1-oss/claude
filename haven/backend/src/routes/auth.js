const express = require("express");
const bcrypt = require("bcryptjs");
const jwt = require("jsonwebtoken");
const { body, validationResult } = require("express-validator");
const supabase = require("../db/supabase");

const router = express.Router();
const MOCK = () => process.env.MOCK_MODE === "true";

function signToken(userId, email) {
  return jwt.sign({ userId, email }, process.env.JWT_SECRET, { expiresIn: "30d" });
}

// POST /auth/signup
router.post(
  "/signup",
  [
    body("email").isEmail().normalizeEmail(),
    body("password").isLength({ min: 8 }),
  ],
  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) return res.status(400).json({ errors: errors.array() });

    const { email, password } = req.body;

    if (MOCK()) {
      const mockId = "mock-user-" + email.replace(/[^a-z0-9]/gi, "");
      return res.json({
        token: signToken(mockId, email),
        user: { id: mockId, email, kyc_status: "pending" },
      });
    }

    try {
      const hash = await bcrypt.hash(password, 12);
      const { data: user, error } = await supabase
        .from("users")
        .insert({ email, password_hash: hash })
        .select("id, email, kyc_status")
        .single();

      if (error) {
        if (error.code === "23505") return res.status(409).json({ error: "Email already registered" });
        throw error;
      }

      // Create wallet row
      await supabase.from("wallets").insert({ user_id: user.id });

      return res.json({ token: signToken(user.id, user.email), user });
    } catch (err) {
      console.error(err);
      return res.status(500).json({ error: "Signup failed" });
    }
  }
);

// POST /auth/login
router.post(
  "/login",
  [body("email").isEmail().normalizeEmail(), body("password").notEmpty()],
  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) return res.status(400).json({ errors: errors.array() });

    const { email, password } = req.body;

    if (MOCK()) {
      const mockId = "mock-user-" + email.replace(/[^a-z0-9]/gi, "");
      return res.json({
        token: signToken(mockId, email),
        user: { id: mockId, email, kyc_status: "approved", first_name: "Test" },
      });
    }

    try {
      const { data: user, error } = await supabase
        .from("users")
        .select("id, email, password_hash, kyc_status, first_name")
        .eq("email", email)
        .single();

      if (error || !user) return res.status(401).json({ error: "Invalid credentials" });

      const valid = await bcrypt.compare(password, user.password_hash);
      if (!valid) return res.status(401).json({ error: "Invalid credentials" });

      const { password_hash: _, ...safeUser } = user;
      return res.json({ token: signToken(user.id, user.email), user: safeUser });
    } catch (err) {
      console.error(err);
      return res.status(500).json({ error: "Login failed" });
    }
  }
);

// POST /auth/kyc/initiate — triggers Persona KYC flow
router.post("/kyc/initiate", async (req, res) => {
  const header = req.headers.authorization;
  if (!header) return res.status(401).json({ error: "Unauthorized" });
  const token = header.slice(7);
  let userId;
  try {
    ({ userId } = jwt.verify(token, process.env.JWT_SECRET));
  } catch {
    return res.status(401).json({ error: "Invalid token" });
  }

  if (MOCK()) {
    return res.json({
      inquiry_id: "inq_mock_" + userId,
      session_token: "session_mock_abc123",
      template_id: "tmpl_mock",
    });
  }

  try {
    const response = await fetch("https://withpersona.com/api/v1/inquiries", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.PERSONA_API_KEY}`,
        "Content-Type": "application/json",
        "Persona-Version": "2023-01-05",
      },
      body: JSON.stringify({
        data: {
          attributes: {
            "inquiry-template-id": process.env.PERSONA_TEMPLATE_ID,
            "reference-id": userId,
          },
        },
      }),
    });

    const data = await response.json();
    const inquiryId = data?.data?.id;
    const sessionToken = data?.data?.attributes?.["session-token"];

    await supabase
      .from("users")
      .update({ kyc_provider_id: inquiryId })
      .eq("id", userId);

    return res.json({ inquiry_id: inquiryId, session_token: sessionToken });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "KYC initiation failed" });
  }
});

// POST /auth/kyc/webhook — Persona fires this on completion
router.post("/kyc/webhook", express.json(), async (req, res) => {
  // In prod: verify Persona webhook signature
  const { data } = req.body;
  const inquiryId = data?.id;
  const status = data?.attributes?.status; // completed | failed | expired

  if (!inquiryId) return res.status(400).json({ error: "Missing inquiry ID" });

  if (MOCK()) return res.json({ received: true });

  const kycStatus = status === "completed" ? "approved" : "rejected";

  await supabase
    .from("users")
    .update({ kyc_status: kycStatus })
    .eq("kyc_provider_id", inquiryId);

  return res.json({ received: true });
});

module.exports = router;
