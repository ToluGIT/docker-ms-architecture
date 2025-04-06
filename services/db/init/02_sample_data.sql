-- db/init/02_sample_data.sql
-- Populating the database with sample data

-- Insert sample users 
-- Admin has a proper bcrypt hash for password "admin123"
INSERT INTO users (email, username, hashed_password)
VALUES 
    ('admin@example.com', 'admin', '$2b$12$ncfueSK6XCJdS6.A8tpiq.itDi/S4yOuf.bYAvAPgNnPgdRrMT.ci'),
    ('user1@example.com', 'user1', 'user123_hashed'),
    ('user2@example.com', 'user2', 'user234_hashed'),
    ('demo@example.com', 'demo', 'demo123_hashed')
ON CONFLICT (email) DO NOTHING;

-- Insert sample items
INSERT INTO items (name, description, price, is_available, owner_id)
VALUES
    ('Laptop', 'High-performance laptop with 16GB RAM', 1299.99, true, 1),
    ('Smartphone', 'Latest model with 128GB storage', 899.99, true, 1),
    ('Headphones', 'Noise-cancelling wireless headphones', 199.99, true, 2),
    ('Tablet', '10-inch tablet with retina display', 599.99, true, 2),
    ('Smartwatch', 'Fitness tracking smartwatch', 249.99, true, 3),
    ('Camera', 'Digital camera with 24MP sensor', 799.99, false, 3),
    ('Monitor', '27-inch 4K monitor', 349.99, true, 4),
    ('Keyboard', 'Mechanical gaming keyboard', 129.99, true, 4),
    ('Mouse', 'Wireless ergonomic mouse', 49.99, true, 1),
    ('Speakers', 'Bluetooth speakers with deep bass', 89.99, true, 2)
ON CONFLICT DO NOTHING;

-- Output a message when data loading is complete
DO $$
BEGIN
    RAISE NOTICE 'Sample data has been loaded successfully.';
END $$;
