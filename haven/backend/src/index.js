require("dotenv").config();
const express = require("express");
const cors = require("cors");
const morgan = require("morgan");

const authRoutes = require("./routes/auth");
const walletRoutes = require("./routes/wallet");
const depositRoutes = require("./routes/deposit");
const withdrawRoutes = require("./routes/withdraw");
const yieldRoutes = require("./routes/yield");
const apyRoutes = require("./routes/apy");
const { authMiddleware } = require("./middleware/auth");

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(morgan("dev"));

// Stripe webhook needs raw body — must come before express.json()
app.use("/deposit/webhook", express.raw({ type: "application/json" }));

app.use(express.json());

// Public routes
app.use("/auth", authRoutes);

// Protected routes
app.use("/wallet", authMiddleware, walletRoutes);
app.use("/deposit", depositRoutes);      // /deposit/webhook is public (Stripe signed)
app.use("/withdraw", authMiddleware, withdrawRoutes);
app.use("/yield", authMiddleware, yieldRoutes);
app.use("/apy", apyRoutes);

app.get("/health", (_req, res) => res.json({ status: "ok", mock: process.env.MOCK_MODE === "true" }));

app.listen(PORT, () => {
  console.log(`Haven API running on port ${PORT} [MOCK_MODE=${process.env.MOCK_MODE}]`);
});

module.exports = app;
