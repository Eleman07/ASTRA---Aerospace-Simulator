const COMPONENTS = {
  5121: { bytes: 1, read: (v, o) => v.getUint8(o), norm: x => x / 255 },
  5123: { bytes: 2, read: (v, o) => v.getUint16(o, true), norm: x => x / 65535 },
  5125: { bytes: 4, read: (v, o) => v.getUint32(o, true) },
  5126: { bytes: 4, read: (v, o) => v.getFloat32(o, true) },
  5120: { bytes: 1, read: (v, o) => v.getInt8(o), norm: x => Math.max(-1, x / 127) },
  5122: { bytes: 2, read: (v, o) => v.getInt16(o, true), norm: x => Math.max(-1, x / 32767) }
};
const WIDTHS = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT4: 16 };

function multiply(a, b) {
  const o = new Float32Array(16);
  for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++)
    o[c * 4 + r] = a[r] * b[c * 4] + a[4 + r] * b[c * 4 + 1] + a[8 + r] * b[c * 4 + 2] + a[12 + r] * b[c * 4 + 3];
  return o;
}
function localMatrix(node) {
  if (node.matrix) return new Float32Array(node.matrix);
  const [x, y, z, w] = node.rotation || [0, 0, 0, 1], [sx, sy, sz] = node.scale || [1, 1, 1], [tx, ty, tz] = node.translation || [0, 0, 0];
  const x2 = x + x, y2 = y + y, z2 = z + z, xx = x * x2, xy = x * y2, xz = x * z2;
  const yy = y * y2, yz = y * z2, zz = z * z2, wx = w * x2, wy = w * y2, wz = w * z2;
  return new Float32Array([
    (1 - yy - zz) * sx, (xy + wz) * sx, (xz - wy) * sx, 0,
    (xy - wz) * sy, (1 - xx - zz) * sy, (yz + wx) * sy, 0,
    (xz + wy) * sz, (yz - wx) * sz, (1 - xx - yy) * sz, 0,
    tx, ty, tz, 1
  ]);
}
function transform(m, x, y, z) {
  return [m[0] * x + m[4] * y + m[8] * z + m[12], m[1] * x + m[5] * y + m[9] * z + m[13], m[2] * x + m[6] * y + m[10] * z + m[14]];
}
function transformNormal(m, x, y, z) {
  const det = determinant3(m);
  if (!Number.isFinite(det) || Math.abs(det) < 1e-20) return null;
  const nx = ((m[5] * m[10] - m[9] * m[6]) * x + (m[9] * m[2] - m[1] * m[10]) * y + (m[1] * m[6] - m[5] * m[2]) * z) / det;
  const ny = ((m[8] * m[6] - m[4] * m[10]) * x + (m[0] * m[10] - m[8] * m[2]) * y + (m[4] * m[2] - m[0] * m[6]) * z) / det;
  const nz = ((m[4] * m[9] - m[8] * m[5]) * x + (m[8] * m[1] - m[0] * m[9]) * y + (m[0] * m[5] - m[4] * m[1]) * z) / det;
  const length = Math.hypot(nx, ny, nz);
  return Number.isFinite(length) && length > 1e-20 ? [nx / length, ny / length, nz / length] : null;
}
function determinant3(m) {
  return m[0] * (m[5] * m[10] - m[9] * m[6]) - m[4] * (m[1] * m[10] - m[9] * m[2]) + m[8] * (m[1] * m[6] - m[5] * m[2]);
}
function decodeDataUri(uri) {
  const match = /^data:([^;,]+)?(;base64)?,(.*)$/s.exec(uri);
  if (!match) throw new Error("URI incorporato non valido nel GLB.");
  const raw = match[2] ? atob(match[3]) : decodeURIComponent(match[3]);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i) & 255;
  return { bytes, mimeType: match[1] || "application/octet-stream" };
}

/** Read a self-contained glTF 2.0 binary file without network requests or third-party code. */
export function parseGlb(buffer, { maxTriangles = 180_000, maxPrimitives = 96, maxVertices = 400_000 } = {}) {
  const bytes = new Uint8Array(buffer), view = new DataView(buffer);
  if (bytes.byteLength < 20 || view.getUint32(0, true) !== 0x46546c67) throw new Error("Il file non è un GLB valido.");
  if (view.getUint32(4, true) !== 2) throw new Error("ASTRA importa modelli binari glTF 2.0 (.glb).");
  const declaredLength = view.getUint32(8, true);
  if (declaredLength > bytes.length || declaredLength < 20) throw new Error("Dimensione GLB non valida o file incompleto.");
  let offset = 12, json = null, binary = new Uint8Array();
  while (offset + 8 <= declaredLength) {
    const length = view.getUint32(offset, true), type = view.getUint32(offset + 4, true), start = offset + 8;
    if (length > declaredLength - start) throw new Error("Chunk GLB troncato.");
    if (type === 0x4e4f534a) json = new TextDecoder().decode(bytes.subarray(start, start + length)).replace(/[\u0000\u0020]+$/g, "");
    if (type === 0x004e4942) binary = bytes.subarray(start, start + length);
    offset = start + length;
  }
  if (!json) throw new Error("Il GLB non contiene il chunk JSON.");
  let doc;
  try { doc = JSON.parse(json); } catch { throw new Error("Il JSON interno del GLB non è leggibile."); }
  if (doc.asset?.version !== "2.0") throw new Error("È richiesto un modello glTF versione 2.0.");
  if ((doc.buffers || []).length > 1 || (doc.buffers || []).some(b => b.uri && !b.uri.startsWith("data:"))) throw new Error("Il modello usa file esterni. Esporta un GLB autonomo con mesh e texture incorporate.");
  let bufferData = binary;
  if (!bufferData.length && doc.buffers?.[0]?.uri?.startsWith("data:")) bufferData = decodeDataUri(doc.buffers[0].uri).bytes;
  const accessors = doc.accessors || [], views = doc.bufferViews || [];
  function readAccessor(index, expected) {
    const acc = accessors[index];
    if (!acc || acc.sparse) throw new Error("Accessor glTF non supportato o incompleto.");
    const width = WIDTHS[acc.type], type = COMPONENTS[acc.componentType], bv = views[acc.bufferView];
    if (!width || !type || !bv || (expected && acc.type !== expected)) throw new Error("Attributo del modello con formato non supportato.");
    const stride = bv.byteStride || width * type.bytes, base = (bv.byteOffset || 0) + (acc.byteOffset || 0);
    if (stride < width * type.bytes || base + Math.max(0, acc.count - 1) * stride + width * type.bytes > bufferData.length) throw new Error("Attributo del modello fuori dai limiti del file.");
    const data = new DataView(bufferData.buffer, bufferData.byteOffset, bufferData.byteLength), out = new Float32Array(acc.count * width);
    for (let i = 0; i < acc.count; i++) for (let c = 0; c < width; c++) {
      const raw = type.read(data, base + i * stride + c * type.bytes);
      out[i * width + c] = acc.normalized && type.norm ? type.norm(raw) : raw;
    }
    return { values: out, count: acc.count, width, componentType: acc.componentType };
  }
  function indicesFor(primitive, vertexCount) {
    if (primitive.indices === undefined) return Array.from({ length: vertexCount }, (_, i) => i);
    const acc = accessors[primitive.indices], raw = readAccessor(primitive.indices, "SCALAR");
    if (![5121, 5123, 5125].includes(raw.componentType)) throw new Error("Indice mesh con tipo non supportato.");
    return Array.from(raw.values, Number);
  }
  const imageBlobs = (doc.images || []).map(image => {
    if (image.bufferView !== undefined) {
      const bv = views[image.bufferView];
      if (!bv) throw new Error("Texture GLB incompleta.");
      const start = bv.byteOffset || 0, end = start + bv.byteLength;
      if (end > bufferData.length) throw new Error("Texture oltre i limiti del GLB.");
      return new Blob([bufferData.slice(start, end)], { type: image.mimeType || "image/png" });
    }
    if (image.uri?.startsWith("data:")) { const decoded = decodeDataUri(image.uri); return new Blob([decoded.bytes], { type: decoded.mimeType }); }
    throw new Error("Una texture dipende da un file esterno. Incorpora le texture nel GLB prima di importarlo.");
  });
  const materialWarnings=[];
  const materialData = (doc.materials || []).map(material => {
    const imageFor=info=>{if(!info)return null;const image=doc.textures?.[info.index]?.source;if(!Number.isInteger(image)||!imageBlobs[image])throw Error('Texture glTF non valida');if((info.texCoord??0)!==0||info.extensions?.KHR_texture_transform){materialWarnings.push('Mappa aggiuntiva omessa: supportato solo TEXCOORD_0 senza trasformazione');return null;}return image;};
    const pbr = material.pbrMetallicRoughness || {};
    const textureRef = pbr.baseColorTexture?.index;
    const imageIndex = textureRef === undefined ? null : doc.textures?.[textureRef]?.source;
    if (textureRef !== undefined && imageIndex === undefined) throw new Error("Riferimento texture glTF non valido.");
    const mrRef=pbr.metallicRoughnessTexture?.index;
    const mrImage=mrRef===undefined?null:doc.textures?.[mrRef]?.source;
    if(mrRef!==undefined && (!Number.isInteger(mrImage)||!imageBlobs[mrImage])) throw new Error("Texture metallic/roughness GLB non valida.");
    return { metallicFactor:pbr.metallicFactor??1, roughnessFactor:pbr.roughnessFactor??1,
      normalTextureIndex:imageFor(material.normalTexture),normalScale:material.normalTexture?.scale??1,
      occlusionTextureIndex:imageFor(material.occlusionTexture),occlusionStrength:material.occlusionTexture?.strength??1,
      emissiveTextureIndex:imageFor(material.emissiveTexture),
      metalRoughTextureIndex:mrImage, emissiveFactor:material.emissiveFactor||[0,0,0], color: pbr.baseColorFactor || [1, 1, 1, 1], textureIndex: imageIndex, alphaMode: material.alphaMode || "OPAQUE", alphaCutoff: material.alphaCutoff ?? 0.5, doubleSided: !!material.doubleSided };
  });
  const rawPrimitives = [], bounds = [[Infinity, Infinity, Infinity], [-Infinity, -Infinity, -Infinity]];
  let totalTriangles = 0, totalVertices = 0;
  function collectMesh(meshIndex, world, nodeName) {
    const mesh = doc.meshes?.[meshIndex];
    if (!mesh) throw new Error("Nodo collegato a una mesh inesistente.");
    for (const prim of mesh.primitives || []) {
      if (prim.mode !== undefined && prim.mode !== 4 && prim.mode !== 5 && prim.mode !== 6) continue;
      if (prim.extensions?.KHR_draco_mesh_compression) throw new Error("Questo GLB usa Draco. Esporta le mesh senza compressione Draco per l’importazione ASTRA.");
      const positionRef = prim.attributes?.POSITION;
      if (positionRef === undefined) continue;
      const position = readAccessor(positionRef, "VEC3"), p = new Float32Array(position.count * 3);
      let transformedNormals = null;
      if (prim.attributes.NORMAL !== undefined) {
        const sourceNormals = readAccessor(prim.attributes.NORMAL, "VEC3");
        if (sourceNormals.count !== position.count) throw new Error("Normali GLB non corrispondenti ai vertici della mesh.");
        transformedNormals = new Float32Array(position.count * 3);
        for (let i = 0; i < position.count; i++) {
          const normal = transformNormal(world, sourceNormals.values[i * 3], sourceNormals.values[i * 3 + 1], sourceNormals.values[i * 3 + 2]);
          if (!normal) { transformedNormals = null; break; }
          transformedNormals.set(normal, i * 3);
        }
      }
      totalVertices += position.count;
      if (totalVertices > maxVertices) throw new Error("Modello troppo dettagliato per il profilo prestazioni di questo dispositivo.");
      for (let i = 0; i < position.count; i++) {
        const q = transform(world, position.values[i * 3], position.values[i * 3 + 1], position.values[i * 3 + 2]);
        for (let c = 0; c < 3; c++) { p[i * 3 + c] = q[c]; bounds[0][c] = Math.min(bounds[0][c], q[c]); bounds[1][c] = Math.max(bounds[1][c], q[c]); }
      }
      let idx = indicesFor(prim, position.count);
      if (prim.mode === 5) { const out = []; for (let i = 2; i < idx.length; i++) (i % 2 ? out.push(idx[i - 1], idx[i - 2], idx[i]) : out.push(idx[i - 2], idx[i - 1], idx[i])); idx = out; }
      if (prim.mode === 6) { const out = []; for (let i = 2; i < idx.length; i++) out.push(idx[0], idx[i - 1], idx[i]); idx = out; }
      if (idx.length % 3) throw new Error("Mesh triangolare incompleta.");
      const triangles = idx.length / 3; totalTriangles += triangles;
      if (totalTriangles > maxTriangles) throw new Error("Modello troppo dettagliato per mantenere la fluidità. Riduci i poligoni ed esporta di nuovo.");
      if (idx.some(i => i >= position.count)) throw new Error("La mesh contiene indici non validi.");
      if (determinant3(world) < 0) for (let i = 0; i < idx.length; i += 3) [idx[i + 1], idx[i + 2]] = [idx[i + 2], idx[i + 1]];
      let uvs = new Float32Array(position.count * 2);
      if (prim.attributes.TEXCOORD_0 !== undefined) {
        const uv = readAccessor(prim.attributes.TEXCOORD_0, "VEC2");
        if (uv.count !== position.count) throw new Error("Coordinate texture non corrispondenti alla mesh.");
        uvs = uv.values;
      }
      rawPrimitives.push({ positions: p, normals: transformedNormals, indices: idx, uvs,
                           materialIndex: prim.material ?? -1, nodeName });
      if (rawPrimitives.length > maxPrimitives) throw new Error("Il modello ha troppi materiali/parti per questo dispositivo.");
    }
  }
  const scene = doc.scenes?.[doc.scene ?? 0], roots = scene?.nodes || (doc.nodes || []).map((_, i) => i).filter(i => !(doc.nodes || []).some(n => n.children?.includes(i)));
  if (!roots.length) throw new Error("Il GLB non contiene una scena 3D valida.");
  const visiting = new Set();
  function visit(index, parent) {
    const node = doc.nodes?.[index];
    if (!node || visiting.has(index)) throw new Error("Gerarchia nodi del GLB non valida.");
    visiting.add(index);
    const world = multiply(parent, localMatrix(node));
    if (node.mesh !== undefined) collectMesh(node.mesh, world, node.name || "");
    for (const child of node.children || []) visit(child, world);
    visiting.delete(index);
  }
  for (const root of roots) visit(root, new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]));
  if (!rawPrimitives.length || !Number.isFinite(bounds[0][0])) throw new Error("Non ho trovato mesh triangolari visibili nel GLB.");
  const center = bounds[0].map((v, i) => (v + bounds[1][i]) * 0.5), maxDim = Math.max(...bounds[1].map((v, i) => v - bounds[0][i]));
  if (!(maxDim > 1e-8 && Number.isFinite(maxDim))) throw new Error("Il modello ha dimensioni nulle o non finite.");
  const fit = 1.8 / maxDim;
  const primitives = rawPrimitives.map(raw => {
    const positions = raw.positions;
    for (let i = 0; i < positions.length; i += 3) for (let c = 0; c < 3; c++) positions[i + c] = (positions[i + c] - center[c]) * fit;
    let normals = raw.normals;
    if (!normals) {
      normals = new Float32Array(positions.length);
      const idx = raw.indices;
      for (let i = 0; i < idx.length; i += 3) {
        const a = idx[i] * 3, b = idx[i + 1] * 3, c = idx[i + 2] * 3;
        const ab = [positions[b] - positions[a], positions[b + 1] - positions[a + 1], positions[b + 2] - positions[a + 2]], ac = [positions[c] - positions[a], positions[c + 1] - positions[a + 1], positions[c + 2] - positions[a + 2]];
        const nx = ab[1] * ac[2] - ab[2] * ac[1], ny = ab[2] * ac[0] - ab[0] * ac[2], nz = ab[0] * ac[1] - ab[1] * ac[0];
        for (const j of [a, b, c]) { normals[j] += nx; normals[j + 1] += ny; normals[j + 2] += nz; }
      }
      for (let i = 0; i < normals.length; i += 3) { const length = Math.hypot(normals[i], normals[i + 1], normals[i + 2]) || 1; normals[i] /= length; normals[i + 1] /= length; normals[i + 2] /= length; }
    }
    return { positions, normals, uvs: raw.uvs, indices: raw.indices,
             materialIndex: raw.materialIndex, nodeName: raw.nodeName,
             material: raw.materialIndex < 0 ? { color: [0.78, 0.82, 0.9, 1], textureIndex: null, alphaMode: "OPAQUE", alphaCutoff: 0.5, doubleSided: false } : materialData[raw.materialIndex] };
  });
  return { primitives, images: imageBlobs, warnings:[...new Set(materialWarnings)], bounds: bounds.map(v => v.slice()), dimensions: bounds[0].map((x, c) => bounds[1][c] - x), normalization: { center, fitScale: fit }, triangles: totalTriangles, vertices: totalVertices };
}
