ALTER TABLE ai_calls DROP CONSTRAINT ai_calls_purpose_check;
ALTER TABLE ai_calls ADD CONSTRAINT ai_calls_purpose_check
    CHECK (purpose IN ('vision', 'embedding', 'text'));
