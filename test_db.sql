-- Count users in the system
SELECT COUNT(*) AS total_users FROM users;

-- Count items in the system
SELECT COUNT(*) AS total_items FROM items;

-- List all users with their item counts
SELECT 
    u.id, 
    u.username, 
    u.email, 
    COUNT(i.id) AS item_count,
    SUM(i.price) AS total_value
FROM 
    users u
LEFT JOIN 
    items i ON u.id = i.owner_id
GROUP BY 
    u.id, u.username, u.email
ORDER BY 
    u.id;

-- Show available items with their owners
SELECT 
    i.id, 
    i.name, 
    i.price, 
    u.username AS owner
FROM 
    items i
JOIN 
    users u ON i.owner_id = u.id
WHERE 
    i.is_available = true
ORDER BY 
    i.price DESC;