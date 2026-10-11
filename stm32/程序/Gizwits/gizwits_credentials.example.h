#ifndef GIZWITS_CREDENTIALS_H
#define GIZWITS_CREDENTIALS_H

/* Copy to gizwits_credentials.h and replace both placeholders with the
 * 32-character values from this product's Gizwits developer console. */
#define PRODUCT_KEY "REPLACE_WITH_32_CHARACTER_PRODUCT_KEY"
#define PRODUCT_SECRET "REPLACE_WITH_32_CHARACTER_PRODUCT_SECRET"

typedef char gizwits_product_key_must_be_32_chars[(sizeof(PRODUCT_KEY) == 33u) ? 1 : -1];
typedef char gizwits_product_secret_must_be_32_chars[(sizeof(PRODUCT_SECRET) == 33u) ? 1 : -1];

#endif
