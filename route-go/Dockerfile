FROM golang:1.27-bookworm AS builder

WORKDIR /src

COPY go.mod ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -o /out/route-go .

FROM gcr.io/distroless/static-debian12:nonroot

COPY --from=builder /out/route-go /route-go

USER 65532:65532

ENTRYPOINT ["/route-go"]