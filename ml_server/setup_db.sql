CREATE DATABASE IF NOT EXISTS leafscan;
USE leafscan;

CREATE TABLE IF NOT EXISTS users (
    user_id      INT AUTO_INCREMENT PRIMARY KEY,
    first_name   VARCHAR(100) NOT NULL,
    last_name    VARCHAR(100) NOT NULL,
    email        VARCHAR(150) UNIQUE NOT NULL,
    password     VARCHAR(255) NOT NULL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS plants (
    plant_id      INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL,
    image_path    VARCHAR(255) NOT NULL,
    upload_date   DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_plants_user
        FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS predictions (
    prediction_id  INT AUTO_INCREMENT PRIMARY KEY,
    plant_id       INT NOT NULL,
    disease_name   VARCHAR(150) NOT NULL,
    confidence     FLOAT NOT NULL,
    result_date    DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_predictions_plant
        FOREIGN KEY (plant_id) REFERENCES plants(plant_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_plants_user_id ON plants(user_id);
CREATE INDEX idx_predictions_plant_id ON predictions(plant_id);

SHOW TABLES;

