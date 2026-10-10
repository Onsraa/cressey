import express from "express";
import pg from "pg";

const app = express();
const pool = new pg.Pool({ connectionString: process.env.DATABASE_URL });

app.get("/health", async (_req, res) => {
  try {
    await pool.query("SELECT 1");
    res.json({ ok: true });
  } catch (err) {
    // On staging this is where it fails: password authentication failed for user "postgres".
    res.status(500).json({ ok: false, error: String(err) });
  }
});

app.get("/customers", async (_req, res) => {
  const { rows } = await pool.query("SELECT id, email FROM customers ORDER BY id");
  res.json(rows);
});

const port = process.env.PORT || 3000;
app.listen(port, () => console.log(`pocketos-api on :${port}`));
