FROM golang:1.22 AS build
WORKDIR /src
COPY go.mod main.go ./
RUN CGO_ENABLED=0 go build -o /route-go .

FROM gcr.io/distroless/static-debian12
COPY --from=build /route-go /route-go
EXPOSE 8080
ENTRYPOINT ["/route-go"]