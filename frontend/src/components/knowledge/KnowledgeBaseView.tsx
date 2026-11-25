import React, { useState, useEffect } from 'react';
import { 
  UploadCloud, 
  FileText, 
  Trash2, 
  Search, 
  Sparkles, 
  Layers, 
  CheckCircle, 
  AlertCircle,
  Database,
  ExternalLink
} from 'lucide-react';
import { DocumentItem, DocumentDetail, SearchResultItem } from '../../types';
import { api } from '../../services/api';

interface KnowledgeBaseViewProps {
  onRefreshStats: () => void;
}

export const KnowledgeBaseView: React.FC<KnowledgeBaseViewProps> = ({ onRefreshStats }) => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  
  // Upload states
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [customTitle, setCustomTitle] = useState<string>('');
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Chunk inspection
  const [inspectedDoc, setInspectedDoc] = useState<DocumentDetail | null>(null);
  const [loadingChunks, setLoadingChunks] = useState<boolean>(false);

  // RAG Query Tester
  const [testQuery, setTestQuery] = useState<string>('How long does standard delivery take?');
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [searching, setSearching] = useState<boolean>(false);
  const [searchHasExecuted, setSearchHasExecuted] = useState<boolean>(false);

  const loadDocuments = async () => {
    setLoading(true);
    try {
      const data = await api.getDocuments();
      setDocuments(data);
    } catch (err) {
      console.error('Failed to load documents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setUploading(true);
    setUploadError(null);
    try {
      await api.uploadDocument(selectedFile, customTitle || undefined);
      setSelectedFile(null);
      setCustomTitle('');
      await loadDocuments();
      onRefreshStats();
    } catch (err: any) {
      console.error('Upload error:', err);
      setUploadError(err?.response?.data?.detail || 'Failed to parse and embed document.');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this document and all its indexed chunks?')) return;
    try {
      await api.deleteDocument(id);
      if (inspectedDoc?.id === id) setInspectedDoc(null);
      await loadDocuments();
      onRefreshStats();
    } catch (err) {
      console.error('Delete document failed:', err);
    }
  };

  const handleInspectChunks = async (id: number) => {
    setLoadingChunks(true);
    try {
      const detail = await api.getDocument(id);
      setInspectedDoc(detail);
    } catch (err) {
      console.error('Failed to inspect chunks:', err);
    } finally {
      setLoadingChunks(false);
    }
  };

  const handleTestSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!testQuery.trim()) return;

    setSearching(true);
    try {
      const results = await api.searchKnowledge(testQuery, 4);
      setSearchResults(results);
      setSearchHasExecuted(true);
    } catch (err) {
      console.error('Search failed:', err);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Overview & Upload Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload Form Card (1 Col) */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center gap-2 mb-3">
            <UploadCloud className="w-5 h-5 text-indigo-600" />
            <h3 className="text-sm font-bold text-slate-900">Upload Policy Document</h3>
          </div>
          <p className="text-xs text-slate-500 mb-4">
            Upload PDF or TXT documents. Text will be extracted, split into semantic chunks, and embedded into the vector index.
          </p>

          <form onSubmit={handleFileUpload} className="space-y-3">
            {uploadError && (
              <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs flex items-center gap-1.5">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{uploadError}</span>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Document File (.pdf, .txt, .md)
              </label>
              <input
                type="file"
                required
                accept=".pdf,.txt,.md"
                onChange={(e) => {
                  const f = e.target.files?.[0] || null;
                  setSelectedFile(f);
                  if (f && !customTitle) {
                    setCustomTitle(f.name.replace(/\.[^/.]+$/, '').replace(/_/g, ' '));
                  }
                }}
                className="w-full text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 cursor-pointer"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Document Title (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Return Policy 2026"
                value={customTitle}
                onChange={(e) => setCustomTitle(e.target.value)}
                className="w-full px-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            <button
              type="submit"
              disabled={uploading || !selectedFile}
              className="w-full py-2 px-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50"
            >
              <UploadCloud className={`w-3.5 h-3.5 ${uploading ? 'animate-bounce' : ''}`} />
              <span>{uploading ? 'Parsing & Embedding Chunks...' : 'Ingest Document'}</span>
            </button>
          </form>
        </div>

        {/* Semantic Search Tester Card (2 Cols) */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Search className="w-5 h-5 text-indigo-600" />
                <h3 className="text-sm font-bold text-slate-900">RAG Semantic Search Workbench</h3>
              </div>
              <span className="text-[11px] font-mono text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                Cosine Similarity Search
              </span>
            </div>
            <p className="text-xs text-slate-500 mb-4">
              Test vector queries against indexed chunks to verify retrieval quality before drafting replies.
            </p>

            <form onSubmit={handleTestSearch} className="flex gap-2 mb-4">
              <input
                type="text"
                value={testQuery}
                onChange={(e) => setTestQuery(e.target.value)}
                placeholder="Ask any policy question..."
                className="flex-1 px-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
              <button
                type="submit"
                disabled={searching}
                className="px-4 py-1.5 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 disabled:opacity-50"
              >
                <Search className={`w-3.5 h-3.5 ${searching ? 'animate-spin' : ''}`} />
                <span>{searching ? 'Querying...' : 'Search Index'}</span>
              </button>
            </form>

            {/* Quick Sample Queries */}
            <div className="flex items-center gap-1.5 text-[11px] text-slate-500 mb-3">
              <span>Quick tests:</span>
              <button
                type="button"
                onClick={() => setTestQuery('What is the return window for defective items?')}
                className="underline hover:text-indigo-600"
              >
                Return window
              </button>
              <span>•</span>
              <button
                type="button"
                onClick={() => setTestQuery('Does warranty cover accidental water spill on headset?')}
                className="underline hover:text-indigo-600"
              >
                Warranty coverage
              </button>
              <span>•</span>
              <button
                type="button"
                onClick={() => setTestQuery('DHL Express shipping delivery timeframes')}
                className="underline hover:text-indigo-600"
              >
                Shipping time
              </button>
            </div>
          </div>

          {/* Search Results Display */}
          <div className="overflow-y-auto max-h-48 space-y-2 mt-2">
            {searchHasExecuted && searchResults.length === 0 && (
              <div className="p-4 bg-amber-50 rounded-lg border border-amber-200 text-xs text-amber-800 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>
                  No chunks passed the relevance threshold (0.28). Knowledge base does not contain sufficient information for this query.
                </span>
              </div>
            )}

            {searchResults.map((r, i) => (
              <div key={i} className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs">
                <div className="flex items-center justify-between font-semibold text-slate-800 mb-1">
                  <span>📄 {r.document_title} (Chunk #{r.chunk_index})</span>
                  <span className="font-mono text-indigo-700 bg-indigo-100/70 px-2 py-0.5 rounded text-[10px]">
                    Similarity: {(r.similarity_score * 100).toFixed(1)}%
                  </span>
                </div>
                <p className="text-slate-600 text-[11px] leading-relaxed italic bg-white p-2 rounded border border-slate-100">
                  "{r.content}"
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Document Library Table */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Indexed Knowledge Documents</h3>
            <p className="text-xs text-slate-500">
              Active documents used for grounding customer response drafts
            </p>
          </div>
          <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-2.5 py-1 rounded-md">
            {documents.length} Document{documents.length !== 1 ? 's' : ''}
          </span>
        </div>

        {loading ? (
          <div className="p-6 text-center text-xs text-slate-400">Loading documents...</div>
        ) : documents.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400">
            No documents uploaded yet. Use the upload card above.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider text-[10px] border-y border-slate-200">
                <tr>
                  <th className="py-2.5 px-3">Title & File</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">File Size</th>
                  <th className="py-2.5 px-3">Chunks</th>
                  <th className="py-2.5 px-3">Ingested On</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50/80">
                    <td className="py-3 px-3">
                      <div className="font-semibold text-slate-900">{doc.title}</div>
                      <div className="text-[11px] text-slate-400 font-mono">{doc.file_name}</div>
                    </td>
                    <td className="py-3 px-3">
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-slate-100 text-slate-700 font-semibold">
                        {doc.file_type}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-600 font-mono">
                      {(doc.file_size_bytes / 1024).toFixed(1)} KB
                    </td>
                    <td className="py-3 px-3">
                      <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-indigo-50 text-indigo-700 font-mono">
                        {doc.chunk_count} chunks
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-500 font-mono">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-3 text-right space-x-2">
                      <button
                        onClick={() => handleInspectChunks(doc.id)}
                        className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-[11px] font-medium transition-colors"
                      >
                        Inspect Chunks
                      </button>
                      <button
                        onClick={() => handleDelete(doc.id)}
                        className="p-1 hover:bg-rose-50 text-slate-400 hover:text-rose-600 rounded transition-colors"
                        title="Delete document"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Chunks Inspection Slide-over / Modal */}
      {inspectedDoc && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[85vh] shadow-2xl border border-slate-200 overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <div>
                <h4 className="text-sm font-bold text-slate-900">
                  Extracted Vector Chunks: {inspectedDoc.title}
                </h4>
                <p className="text-xs text-slate-500">
                  Total {inspectedDoc.chunks.length} chunks embedded in the vector store
                </p>
              </div>
              <button
                onClick={() => setInspectedDoc(null)}
                className="text-slate-400 hover:text-slate-600 font-bold p-1"
              >
                ✕
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-3 flex-1">
              {inspectedDoc.chunks.map((chunk) => (
                <div key={chunk.id} className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs">
                  <div className="flex items-center justify-between font-mono text-[10px] text-slate-500 mb-1">
                    <span>Chunk #{chunk.chunk_index} (ID: {chunk.id})</span>
                    <span>{chunk.metadata_info?.words_count || 0} words</span>
                  </div>
                  <p className="text-slate-800 whitespace-pre-wrap leading-relaxed font-sans">
                    {chunk.content}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
