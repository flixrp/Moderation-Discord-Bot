# ************************************
# SQL-Script to create the required database and tables to run the discord bot
#
# Copyright 2022 Phil
# (https://github.com/Commandserver)
# ************************************
CREATE SCHEMA IF NOT EXISTS flix_bot;

USE flix_bot;

CREATE TABLE IF NOT EXISTS Guild (
    id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT 'The Identifier',
    created_at TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP() COMMENT 'Creation datetime in UTC',
    guild_id   BIGINT UNSIGNED NOT NULL COMMENT 'Discord ID of the guild'
) COMMENT 'The Guild data for multi guild ability';

CREATE TABLE IF NOT EXISTS Mute (
    id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT 'The Identifier',
    guild_id   INT UNSIGNED            NOT NULL,
    FOREIGN KEY (guild_id) REFERENCES Guild (id)
        ON DELETE CASCADE,
    created_at TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP() COMMENT 'Creation datetime in UTC',
    actor      BIGINT UNSIGNED NOT NULL COMMENT 'Discord ID of the team member who triggered the mute/unmute',
    `subject`  BIGINT UNSIGNED NOT NULL COMMENT 'Discord ID of the member who got mute/unmute',
    duration   DATETIME        NULL COMMENT 'The datetime in UTC until the user got muted',
    reason     VARCHAR(512)    NULL COMMENT 'The reason why the member got muted/unmuted',
    is_mute    BOOLEAN         NOT NULL DEFAULT FALSE COMMENT 'Whether the actor unmuted or muted the user'
) COMMENT 'Member mutes';

CREATE TABLE IF NOT EXISTS Supporter (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT 'The Identifier',
    guild_id   INT UNSIGNED            NOT NULL,
    FOREIGN KEY (guild_id) REFERENCES Guild (id)
        ON DELETE CASCADE,
    created_at     TIMESTAMP DEFAULT NOW() NOT NULL COMMENT 'Creation datetime',
    discord_id     BIGINT UNSIGNED UNIQUE  NOT NULL COMMENT 'The discord User-ID',
    last_activity  TIMESTAMP DEFAULT NOW() NOT NULL COMMENT 'The last activity on the discord',
    left_at        TIMESTAMP               NULL COMMENT 'The timestamp when he left and is no longer a team member',
    remind_message VARCHAR(2000)           NULL COMMENT 'Message used for /remind command'
);

CREATE TABLE IF NOT EXISTS Unban (
    id           INT UNSIGNED            NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT 'The Identifier',
    created_at   TIMESTAMP DEFAULT NOW() NOT NULL COMMENT 'Creation datetime / unbanned at',

    reason       VARCHAR(1000)           NULL COMMENT 'The reason of this previous ban',

    user_id      BIGINT UNSIGNED         NOT NULL COMMENT 'Banned discord user id',
    supporter_fk INT UNSIGNED            NULL COMMENT 'Supporter who unbanned',
    unban_reason VARCHAR(1000)           NULL COMMENT 'Reason to unban',
    FOREIGN KEY (supporter_fk) REFERENCES Supporter (id)
        ON UPDATE SET NULL
        ON DELETE SET NULL
) COMMENT 'Unbans which were made with the bot';

CREATE TABLE IF NOT EXISTS MessageDeletion (
    id                    INT UNSIGNED            NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT 'The Identifier',
    created_at            TIMESTAMP DEFAULT NOW() NOT NULL COMMENT 'Creation datetime / deleted at',

    msg_content           VARCHAR(6000)           NULL,
    msg_reference         BIGINT UNSIGNED         NULL,
    msg_created_at        TIMESTAMP               NOT NULL COMMENT 'in UTC',
    msg_author            BIGINT UNSIGNED         NOT NULL,
    msg_channel           BIGINT UNSIGNED         NOT NULL,
    msg_attachment_amount INT UNSIGNED            NOT NULL,
    msg_sticker_amount    INT UNSIGNED            NOT NULL,
    msg_flags             INT UNSIGNED            NOT NULL,

    log_message_jump_url  VARCHAR(255)            NULL COMMENT 'Jump url which allows to jump to the log message',
    supporter_fk          INT UNSIGNED            NULL COMMENT 'Supporter who deleted the message',
    FOREIGN KEY (supporter_fk) REFERENCES Supporter (id)
        ON UPDATE RESTRICT
        ON DELETE SET NULL
) COMMENT 'Message deletions which were made with the bot';

CREATE TABLE IF NOT EXISTS Ban (
    id         INT UNSIGNED            NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT 'The Identifier',
    created_at TIMESTAMP DEFAULT NOW() NOT NULL COMMENT 'Creation datetime / banned at',

    banner_fk  INT UNSIGNED            NOT NULL COMMENT 'Supporter who banned',
    user_id    BIGINT UNSIGNED         NOT NULL COMMENT 'Banned discord user id',
    ban_reason VARCHAR(255)            NOT NULL COMMENT 'Reason for the ban written by the supporter'

    /*unbanner_fk  INT UNSIGNED            NULL COMMENT 'Supporter who unbanned',
    unbanned_at  TIMESTAMP               NULL COMMENT 'Unbanned datetime. The only real indicator if the ban is removed',
    unban_reason VARCHAR(2000)           NULL,
    FOREIGN KEY (banner_fk) REFERENCES Supporter (id)
        ON UPDATE SET NULL
        ON DELETE SET NULL,
    FOREIGN KEY (unbanner_fk) REFERENCES Supporter (id)
        ON UPDATE SET NULL
        ON DELETE SET NULL,
    CONSTRAINT CHK_Unban CHECK (
        IF(
                    unbanner_fk IS NULL XOR unbanned_at IS NULL,
                    FALSE,
                    IF(unbanned_at IS NULL, unban_reason IS NULL, TRUE)
            )
        )*/
) COMMENT 'Bans which were made with the bot';

CREATE TABLE IF NOT EXISTS BanUserRole (
    id      INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT 'The Identifier',
    role_id BIGINT UNSIGNED NOT NULL,
    name    VARCHAR(255) NULL COMMENT 'Name of the role',
    ban_fk  INT UNSIGNED NOT NULL COMMENT 'Related ban',
    FOREIGN KEY (ban_fk) REFERENCES Ban (id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE
) COMMENT 'Represents a role a user had before he got banned';
