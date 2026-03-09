CREATE TABLE IF NOT EXISTS brands (
    id              SERIAL PRIMARY KEY,
    company_name    VARCHAR(255) NOT NULL,
    instagram_handle VARCHAR(255),
    twitter_handle  VARCHAR(255),
    linkedin_url    TEXT,
    industry        VARCHAR(255),
    region          VARCHAR(255),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaigns (
    id                  SERIAL PRIMARY KEY,
    brand_id            INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    product_service     VARCHAR(255),
    icp                 TEXT,                          
    tone                VARCHAR(100),                  
    description         TEXT,                          
    content_type        VARCHAR(255),                  
    ai_brain            JSONB,
    generated_content   JSONB,                         
    status              VARCHAR(50) DEFAULT 'draft',   
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS brand_social_credentials (
    id                   SERIAL PRIMARY KEY,
    brand_id             INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    platform             VARCHAR(20) NOT NULL,  -- 'instagram', 'twitter', 'linkedin'
    access_token         TEXT,
    access_token_secret  TEXT,                  -- Twitter only (OAuth 1.0a)
    api_key              TEXT,                  -- Twitter only
    api_secret           TEXT,                  -- Twitter only
    platform_account_id  TEXT,                  -- Instagram business account ID / LinkedIn person URN
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(brand_id, platform)
);

CREATE INDEX IF NOT EXISTS idx_campaigns_brand_id  ON campaigns(brand_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_status    ON campaigns(status);
CREATE INDEX IF NOT EXISTS idx_brands_company      ON brands(company_name);
