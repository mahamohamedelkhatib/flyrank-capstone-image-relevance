from app.db import connect


def main() -> None:
    with connect() as conn:
        calls, ok, errors, tokens_in, tokens_out, cost, avg_ms = conn.execute(
            """
            SELECT count(*),
                   count(*) FILTER (WHERE status = 'ok'),
                   count(*) FILTER (WHERE status = 'error'),
                   coalesce(sum(input_tokens), 0),
                   coalesce(sum(output_tokens), 0),
                   coalesce(sum(cost_usd), 0),
                   coalesce(avg(latency_ms), 0)
            FROM ai_calls
            """
        ).fetchone()
        missing = conn.execute(
            """
            SELECT filename FROM images i
            WHERE status IN ('done', 'flagged')
              AND NOT EXISTS (
                  SELECT 1 FROM ai_calls c WHERE c.image_id = i.id AND c.status = 'ok'
              )
            ORDER BY filename
            """
        ).fetchall()

    print(f"calls logged:        {calls} ({ok} ok, {errors} errors)")
    print(f"input tokens:        {tokens_in}")
    print(f"output tokens:       {tokens_out}")
    print(f"estimated cost:      ${cost:.6f}")
    print(f"average latency:     {avg_ms:.0f} ms")
    print(f"tagged images with no logged call: {len(missing)}")


if __name__ == "__main__":
    main()
