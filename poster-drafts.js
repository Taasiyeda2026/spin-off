// The original key stays readable for browsers with pre-upgrade drafts.
window.posterDrafts = (() => {
  const databaseName = 'spacetech-poster-drafts';
  const storeName = 'drafts';
  const legacyKey = 'spacetech-poster-v1';

  function open() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(databaseName, 1);
      request.onupgradeneeded = () => request.result.createObjectStore(storeName);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  function keyFor(posterId) {
    if (posterId === null) return legacyKey;
    if (typeof posterId !== 'string' || !posterId.trim()) {
      throw new TypeError('A poster draft requires a nonempty poster ID');
    }
    return 'poster:' + posterId;
  }

  async function transact(posterId, mode, execute) {
    const key = keyFor(posterId);
    const database = await open();
    try {
      return await new Promise((resolve, reject) => {
        const transaction = database.transaction(storeName, mode);
        const request = execute(transaction.objectStore(storeName), key);
        transaction.oncomplete = () => resolve(request.result);
        transaction.onabort = () => reject(transaction.error);
      });
    } finally {
      database.close();
    }
  }

  return {
    read: (posterId) => transact(posterId, 'readonly', (store, key) => store.get(key)),
    write: (posterId, draft) => transact(posterId, 'readwrite', (store, key) => store.put(draft, key)),
    remove: (posterId) => transact(posterId, 'readwrite', (store, key) => store.delete(key)),
  };
})();
