using System;
using System.Threading;
using System.Threading.Tasks;
using System.Collections.Generic;

namespace ModernApp.Storage
{
    public class StorageException : Exception 
    {
        public StorageException(string message) : base(message) {}
    }

    public interface ICloudClient
    {
        Task<bool> UploadAsync(string fileName, byte[] data, CancellationToken ct);
    }

    public class StorageService
    {
        private readonly ICloudClient _client;

        public StorageService(ICloudClient client)
        {
            _client = client;
        }

        public async Task<string> SaveDataAsync(string id, string content, CancellationToken cancellationToken)
        {
            if (string.IsNullOrEmpty(id)) throw new ArgumentNullException(nameof(id));
            if (content == null) return "Empty";

            byte[] data = System.Text.Encoding.UTF8.GetBytes(content);
            
            bool success = await _client.UploadAsync(id + ".txt", data, cancellationToken);
            
            if (!success)
            {
                throw new StorageException("Upload failed");
            }

            return $"Saved:{id}";
        }
    }
}
