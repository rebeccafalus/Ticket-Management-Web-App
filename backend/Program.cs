using Npgsql;

var builder = WebApplication.CreateBuilder(args);
var connectionString = builder.Configuration.GetConnectionString("DefaultConnection")
    ?? throw new InvalidOperationException("DefaultConnection is required.");

builder.Services.AddCors(options => options.AddPolicy("frontend", policy =>
    policy.AllowAnyOrigin().AllowAnyHeader().AllowAnyMethod()));
builder.Services.AddSingleton(_ => NpgsqlDataSource.Create(connectionString));

var app = builder.Build();
app.UseCors("frontend");

app.MapGet("/health", () => Results.Ok(new { status = "ok" }));

app.MapGet("/api/inquiries", async (string? search, string? status, NpgsqlDataSource dataSource) =>
{
    await using var command = dataSource.CreateCommand("""
        SELECT id, title, description, requester_name, requester_email, assignee, status, created_at, updated_at
        FROM inquiries
        WHERE (@search = '' OR title ILIKE '%' || @search || '%' OR description ILIKE '%' || @search || '%' OR requester_name ILIKE '%' || @search || '%' OR requester_email ILIKE '%' || @search || '%')
          AND (@status = '' OR status = @status)
        ORDER BY updated_at DESC;
        """);
    command.Parameters.AddWithValue("search", search?.Trim() ?? "");
    command.Parameters.AddWithValue("status", status?.Trim() ?? "");
    return Results.Ok(await ReadInquiries(command));
});

app.MapGet("/api/inquiries/{id:int}", async (int id, NpgsqlDataSource dataSource) =>
{
    await using var command = dataSource.CreateCommand("SELECT id, title, description, requester_name, requester_email, assignee, status, created_at, updated_at FROM inquiries WHERE id = $1");
    command.Parameters.AddWithValue(id);
    await using var reader = await command.ExecuteReaderAsync();
    return await reader.ReadAsync() ? Results.Ok(MapInquiry(reader)) : Results.NotFound();
});

app.MapPost("/api/inquiries", async (InquiryRequest request, NpgsqlDataSource dataSource) =>
{
    var validation = Validate(request);
    if (validation is not null) return Results.BadRequest(new { message = validation });
    await using var command = dataSource.CreateCommand("""
        INSERT INTO inquiries (title, description, requester_name, requester_email, assignee, status)
        VALUES ($1, $2, $3, $4, NULLIF($5, ''), $6)
        RETURNING id, title, description, requester_name, requester_email, assignee, status, created_at, updated_at;
        """);
    AddRequestParameters(command, request);
    await using var reader = await command.ExecuteReaderAsync();
    await reader.ReadAsync();
    return Results.Created($"/api/inquiries/{reader.GetInt32(0)}", MapInquiry(reader));
});

app.MapPut("/api/inquiries/{id:int}", async (int id, InquiryRequest request, NpgsqlDataSource dataSource) =>
{
    var validation = Validate(request);
    if (validation is not null) return Results.BadRequest(new { message = validation });
    await using var command = dataSource.CreateCommand("""
        UPDATE inquiries
        SET title = $1, description = $2, requester_name = $3, requester_email = $4,
            assignee = NULLIF($5, ''), status = $6, updated_at = NOW()
        WHERE id = $7
        RETURNING id, title, description, requester_name, requester_email, assignee, status, created_at, updated_at;
        """);
    AddRequestParameters(command, request);
    command.Parameters.AddWithValue(id);
    await using var reader = await command.ExecuteReaderAsync();
    return await reader.ReadAsync() ? Results.Ok(MapInquiry(reader)) : Results.NotFound();
});

app.MapPatch("/api/inquiries/{id:int}/assignment", async (int id, AssignmentRequest request, NpgsqlDataSource dataSource) =>
{
    await using var command = dataSource.CreateCommand("UPDATE inquiries SET assignee = NULLIF($1, ''), updated_at = NOW() WHERE id = $2 RETURNING id, title, description, requester_name, requester_email, assignee, status, created_at, updated_at");
    command.Parameters.AddWithValue(request.Assignee?.Trim() ?? "");
    command.Parameters.AddWithValue(id);
    await using var reader = await command.ExecuteReaderAsync();
    return await reader.ReadAsync() ? Results.Ok(MapInquiry(reader)) : Results.NotFound();
});

app.MapPatch("/api/inquiries/{id:int}/status", async (int id, StatusRequest request, NpgsqlDataSource dataSource) =>
{
    if (!ApiConstants.Statuses.Contains(request.Status)) return Results.BadRequest(new { message = "Status must be Open, In Progress, Resolved, or Closed." });
    await using var command = dataSource.CreateCommand("UPDATE inquiries SET status = $1, updated_at = NOW() WHERE id = $2 RETURNING id, title, description, requester_name, requester_email, assignee, status, created_at, updated_at");
    command.Parameters.AddWithValue(request.Status);
    command.Parameters.AddWithValue(id);
    await using var reader = await command.ExecuteReaderAsync();
    return await reader.ReadAsync() ? Results.Ok(MapInquiry(reader)) : Results.NotFound();
});

app.Run();

static string? Validate(InquiryRequest request)
{
    if (string.IsNullOrWhiteSpace(request.Title) || request.Title.Length > 160) return "Title is required and must be 160 characters or fewer.";
    if (string.IsNullOrWhiteSpace(request.Description)) return "Description is required.";
    if (string.IsNullOrWhiteSpace(request.RequesterName)) return "Requester name is required.";
    if (string.IsNullOrWhiteSpace(request.RequesterEmail) || !request.RequesterEmail.Contains('@')) return "A valid requester email is required.";
    if (!ApiConstants.Statuses.Contains(request.Status)) return "Status must be Open, In Progress, Resolved, or Closed.";
    return null;
}

static void AddRequestParameters(NpgsqlCommand command, InquiryRequest request)
{
    command.Parameters.AddWithValue(request.Title.Trim());
    command.Parameters.AddWithValue(request.Description.Trim());
    command.Parameters.AddWithValue(request.RequesterName.Trim());
    command.Parameters.AddWithValue(request.RequesterEmail.Trim());
    command.Parameters.AddWithValue(request.Assignee?.Trim() ?? "");
    command.Parameters.AddWithValue(request.Status);
}

static async Task<List<Inquiry>> ReadInquiries(NpgsqlCommand command)
{
    var inquiries = new List<Inquiry>();
    await using var reader = await command.ExecuteReaderAsync();
    while (await reader.ReadAsync()) inquiries.Add(MapInquiry(reader));
    return inquiries;
}

static Inquiry MapInquiry(NpgsqlDataReader reader) => new(
    reader.GetInt32(0), reader.GetString(1), reader.GetString(2), reader.GetString(3),
    reader.GetString(4), reader.IsDBNull(5) ? null : reader.GetString(5), reader.GetString(6),
    reader.GetDateTime(7), reader.GetDateTime(8));

public record InquiryRequest(string Title, string Description, string RequesterName, string RequesterEmail, string? Assignee, string Status = "Open");
public record AssignmentRequest(string? Assignee);
public record StatusRequest(string Status);
public record Inquiry(int Id, string Title, string Description, string RequesterName, string RequesterEmail, string? Assignee, string Status, DateTime CreatedAt, DateTime UpdatedAt);

public static class ApiConstants
{
    public static readonly string[] Statuses = ["Open", "In Progress", "Resolved", "Closed"];
}