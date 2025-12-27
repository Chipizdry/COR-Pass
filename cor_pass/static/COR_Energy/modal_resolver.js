


import { MODAL_SCHEMAS } from "./modalSchemas.js";

export function resolveModalSchema(vendor, model) {
    const vendorSchemas = MODAL_SCHEMAS[vendor];
    if (!vendorSchemas) return null;

    return vendorSchemas[model] || vendorSchemas.default || null;
}


