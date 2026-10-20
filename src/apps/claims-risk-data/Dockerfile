FROM mcr.microsoft.com/azure-databases/data-api-builder:2.1.5-nonroot
COPY dab-config.json /App/dab-config.json
ENTRYPOINT ["dotnet", "Azure.DataApiBuilder.Service.dll"]
CMD ["--ConfigFileName", "/App/dab-config.json"]
